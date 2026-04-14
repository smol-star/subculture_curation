import os
import json
import re
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# 전역 클라이언트 변수 (지연 초기화)
_client = None

def get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("[AI Error] GEMINI_API_KEY가 환경 변수에 없습니다.")
            return None
        _client = genai.Client(api_key=api_key)
    return _client

def get_available_model():
    """2026년 4월 표준: Gemini 3.1 시리즈 중 무료 티어 최적 모델 선정"""
    client = get_client()
    if not client: return "gemini-3.1-flash-lite" 
    
    try:
        # 가용 모델 목록 조회
        models = [m.name for m in client.models.list()]
        print(f"   [AI] 2026 리얼타임 모델 리스트: {models}")
        
        # 3.1 시리즈 중 무료 티어에서 가장 안정적인 순서
        # (Flash-Lite가 쿼터가 가장 많고 Flash가 그 다음임)
        preferences = [
            'gemini-3.1-flash-lite', 
            'gemini-3.1-flash',
            '3.1-flash',
            '2.0-flash' # 3.1이 없을 경우의 폴백
        ]
        
        selected = None
        for pref in preferences:
            for m in models:
                if pref in m:
                    selected = m
                    break
            if selected: break
            
        if selected:
            print(f"   [AI] ✨ 2026 표준 모델 선택 성공: {selected}")
            return selected
        elif models:
            # 3.1 키워드가 없으면 가용한 모델 중 가장 가벼운 것 선택
            return models[0]
            
    except Exception as e:
        print(f"   [AI Model List Error] {e}")
        
    return "gemini-3.1-flash-lite" # 최후의 보루

def clean_text(text):
    if not text: return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\?[^ ]*', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:1000]

def curate_and_generate_scripts(raw_items):
    """최신 google-genai SDK를 사용한 2단계 큐레이션"""
    client = get_client()
    if not client: return raw_items

    # 1. 모델 결정
    model_id = get_available_model()

    # 결과값 기본 세팅
    for item in raw_items:
        item.setdefault("ai_summary", "[미처리] AI 큐레이션 대기 중")
        item.setdefault("translated_full_text", "[미처리] 번역 대기 중")
        item.setdefault("is_hot", False)

    if not raw_items: return raw_items

    print(f"   [Step 1] 최신 SDK 기반 핫이슈 선별 시작 (대상: {len(raw_items)}개)")
    
    # --- STEP 1: 핫이슈 선별 ---
    step1_system = "너는 글로벌 서브컬처 큐레이터 편집장이다. 결과는 반드시 JSON 배열로만 출력하라."
    step1_content = "아래 리스트 중 유튜브 쇼츠로 만들 만한 자극적인 뉴스 2개 이하를 골라 'content_url' 배열만 반환해.\n\n"
    for item in raw_items:
        step1_content += f"- [URL: {item['content_url']}] 제목: {clean_text(item['title'])}\n"

    hot_urls = []
    try:
        response = client.models.generate_content(
            model=model_id,
            contents=step1_content,
            config=types.GenerateContentConfig(
                system_instruction=step1_system,
                temperature=0.2,
                response_mime_type="application/json"
            )
        )
        # response.text가 직접 JSON일 확률이 높음 (mime_type 설정 시)
        res_text = response.text.strip()
        hot_urls = json.loads(res_text)
    except Exception as e:
        print(f"   [Step 1 AI Failed] {e}")

    print(f"   -> 선정된 핫이슈 개수: {len(hot_urls)}개")

    # --- STEP 2: 정밀 가공 ---
    for item in raw_items:
        if item["content_url"] in hot_urls:
            print(f"   [Step 2] 정밀 대본 가공 중... ({item['title'][:20]}...)")
            item["is_hot"] = True
            
            step2_system = "너는 전문 서브컬처 큐레이터이자 쇼츠 작가이다. 한국어로 응답하며 JSON 객체로 반환하라."
            step2_prompt = f"""원문 제목: {item['title']}\n원문 요약: {item['raw_text']}\n
            위 내용을 바탕으로 'translated_full_text'(통번역)와 'ai_summary'(3~4문장의 쇼츠 대본)를 작성해."""

            try:
                response2 = client.models.generate_content(
                    model=model_id,
                    contents=step2_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=step2_system,
                        temperature=0.7,
                        response_mime_type="application/json"
                    )
                )
                parsed = json.loads(response2.text)
                item["translated_full_text"] = parsed.get("translated_full_text", "번역 실패")
                item["ai_summary"] = parsed.get("ai_summary", "대본 가공 실패")
            except Exception as e:
                item["translated_full_text"] = f"AI 처리 에러: {e}"
                
    return raw_items
