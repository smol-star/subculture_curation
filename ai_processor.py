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

def get_model(preference):
    """지정된 이름과 가장 유사한 모델을 찾아 반환"""
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    for m in available_models:
        if preference in m:
            return genai.GenerativeModel(m)
    return genai.GenerativeModel(available_models[0]) if available_models else None

def curate_and_generate_scripts(raw_items):
    """
    [API 절약형 Two-Step 처리]
    STEP 1: 저렴한 Flash 모델을 이용해 핫 토픽(쇼츠 제작용) URL 2~3개만 선별
    STEP 2: 선별된 원문에만 고성능 Pro 모델을 사용해 전체 번역 및 쇼츠 대본 가공
    """
    if not raw_items or not init_gemini():
        return raw_items
        
    flash_model = get_model('gemini-1.5-flash')
    pro_model = get_model('gemini-1.5-pro')
    
    if not flash_model or not pro_model:
         print("[AI Error] 적합한 제미나이 모델을 찾을 수 없습니다.")
         return raw_items

    print(f"   [Step 1] Flash 모델을 통한 가벼운 1차 핫이슈 선별 시작 (총 {len(raw_items)}개 후보)")
    
    # 1. Flash 필터링 프롬프트
    step1_prompt = """너는 글로벌 서브컬처 큐레이터 편집장이다.
비용 절감을 위해 아래 리스트의 '제목'과 '추천수'만 가볍게 보고, "가장 자극적이고 유튜브 쇼츠로 만들 만한" 파급력 있는 뉴스 2개 이하를 골라라.
결과는 오직 선택된 항목의 'content_url' 값이 담긴 JSON 문자열 리스트(Array of strings)로만 출력해라.

[입력 후보]
"""
    for item in raw_items:
        step1_prompt += f"- [URL: {item['content_url']}] (추천수: {item['engagement_score']}) 제목: {item['title']}\n"
        
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
            
            step2_prompt = f"""너는 '전문 글로벌 서브컬처 큐레이터'이며 유튜브 쇼츠 작가이다.
아래 주어진 원문을 분석하고, 다음 작업들을 수행하여 반환해라.

1. "translated_full_text": 원문 전체의 정밀한 한국어 통번역본 (팩트체크 용도).
2. "ai_summary": 요약을 기반으로 '초반 3초 후킹(Hook)'이 포함된 강력한 유튜브 쇼츠 나레이션 대본 (3~4문장 분량). 

반드시 위 2개 키를 가진 단일 JSON 객체(Dictionary) 구조로 응답해라.
원문 제목: {item['title']}
원문 텍스트: {item['raw_text']}
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
