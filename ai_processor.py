import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def init_gemini():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[AI Error] GEMINI_API_KEY가 없습니다.")
        return False
    genai.configure(api_key=api_key)
    return True

import re

def get_model(preference_list):
    """우선순위 리스트(preference_list)에 따라 가장 적절한 모델을 찾아 반환"""
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    for pref in preference_list:
        for m in available_models:
            if pref in m:
                return genai.GenerativeModel(m)
    return genai.GenerativeModel(available_models[0]) if available_models else None

def clean_text(text):
    if not text: return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\?[^ ]*', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:1000]

def curate_and_generate_scripts(raw_items):
    """
    [API 절약형 Two-Step 처리]
    STEP 1: 저렴한 Flash 모델을 이용해 핫 토픽(쇼츠 제작용) URL 2~3개만 선별
    STEP 2: 선별된 원문에만 고성능 Pro 모델을 사용해 전체 번역 및 쇼츠 대본 가공
    """
    # 항상 BQ 필수 필드가 있도록 기본값 사전 세팅
    for item in raw_items:
        item.setdefault("ai_summary", "[미처리] AI 큐레이션 대기 중")
        item.setdefault("translated_full_text", "[미처리] 번역 대기 중")
        item.setdefault("is_hot", False)

    if not raw_items or not init_gemini():
        return raw_items
        
    flash_model = get_model(['gemini-1.5-flash', 'gemini-2.0-flash', 'gemini-2.5-flash'])
    pro_model = get_model(['gemini-1.5-pro', 'gemini-2.0-pro', 'gemini-pro'])
    
    if not flash_model or not pro_model:
         print("[AI Error] 적합한 제미나이 모델을 찾을 수 없습니다.")
         return raw_items

    print(f"   [Step 1] Flash 모델을 통한 가벼운 1차 핫이슈 선별 시작 (총 {len(raw_items)}개 후보)")
    
    # 1. Flash 필터링 프롬프트
    step1_prompt = """너는 글로벌 서브컬처 큐레이터 편집장이다. 인간처럼 말하지 마라.
비용 절감을 위해 아래 리스트의 '제목'과 '추천수'만 가볍게 보고, "가장 자극적이고 유튜브 쇼츠로 만들 만한" 파급력 있는 뉴스 2개 이하를 골라라.

[출력 규칙 — 최우선 적용]
- 응답의 첫 번째 문자는 반드시 [ 이어야 한다.
- JSON 배열(Array) 외에 어떤 텍스트도 추가하지 마라. "네, 알겠습니다" 같은 문구는 시스템 오류를 낸다.
- 결과는 오직 선택된 항목의 'content_url' 값이 담긴 문자열 배열(예: ["url1", "url2"]) 로만 출력.

[입력 후보]
"""
    for item in raw_items:
        clean_title = clean_text(item['title'])
        step1_prompt += f"- [URL: {item['content_url']}] (추천수: {item['engagement_score']}) 제목: {clean_title}\n"
        
    hot_urls = []
    try:
        res1 = flash_model.generate_content(step1_prompt).text.strip()
        start = res1.find('[')
        end = res1.rfind(']')
        if start != -1 and end != -1:
            hot_urls = json.loads(res1[start:end+1])
    except Exception as e:
        print(f"   [Step 1 AI Failed] {e}")

    print(f"   -> Flash 에 의해 선정된 핫이슈 갯수: {len(hot_urls)}개")

    # 2. Pro 정밀 모드 프롬프트 구성 및 처리
    for item in raw_items:
        if item["content_url"] in hot_urls:
            print(f"   [Step 2] Pro 모델로 정밀 번역 및 대본 가공 중... ({item['title'][:20]}...)")
            item["is_hot"] = True
            
            step2_prompt = f"""너는 '전문 글로벌 서브컬처 큐레이터'이며 유튜브 쇼츠 작가이다. 인간처럼 말하지 마라.
아래 주어진 원문을 분석하고, 다음 작업들을 수행하여 반환해라.

[출력 규칙 — 최우선 적용]
- 응답의 첫 번째 문자는 반드시 {{ 이어야 한다.
- "알겠습니다", "분석 결과입니다" 등의 텍스트를 절대 쓰지 마라.
- 반드시 아래 2개 키를 가진 단일 JSON 객체(Dictionary) 구조로 응답해라.

1. "translated_full_text": 원문 전체의 정밀한 한국어 통번역본 (팩트체크 용도).
2. "ai_summary": 요약을 기반으로 '초반 3초 후킹(Hook)'이 포함된 강력한 유튜브 쇼츠 나레이션 대본 (3~4문장 분량). 

원문 제목: {clean_text(item['title'])}
원문 텍스트: {clean_text(item['raw_text'])}
"""
            try:
                res2 = pro_model.generate_content(step2_prompt).text.strip()
                s = res2.find('{')
                e = res2.rfind('}')
                if s != -1 and e != -1:
                    parsed = json.loads(res2[s:e+1])
                    item["translated_full_text"] = parsed.get("translated_full_text", "번역 실패")
                    item["ai_summary"] = parsed.get("ai_summary", "대본 가공 실패")
                else:
                     item["translated_full_text"] = "JSON 파싱 에러"
                     item["ai_summary"] = res2
            except Exception as e:
                item["translated_full_text"] = f"Pro 모델 반환 에러: {e}"
                item["ai_summary"] = "처리 불가"
        else:
             # 선택받지 못한 항목들
             item["is_hot"] = False
             item["translated_full_text"] = "[비용 절감] Flash 1차 필터링 탈락으로 인해 통번역 생략됨."
             item["ai_summary"] = "[비용 절감] 쇼츠 가치 낮음으로 판정되어 대본 가공 생략."
    
    return raw_items

if __name__ == "__main__":
    pass
