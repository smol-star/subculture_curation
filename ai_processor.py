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
    """사용 가능한 모델 목록을 출력하고 최적의 모델(1.5-flash)을 선택"""
    client = get_client()
    if not client: return "gemini-1.5-flash" # 폴백
    
    try:
        # 새로운 SDK의 모델 리스트 조회 방식
        models = [m.name for m in client.models.list()]
        
        # 429 에러가 잦은 2.0, 2.5, 3.1 시리즈는 제외 (블랙리스트)
        blacklist = ['2.0', '2.5', '3.1', 'pro-latest', 'ultra']
        
        # 안전한 1.5 시리즈 (화이트리스트)
        safe_keywords = ['1.5-flash', '1.5-pro', 'gemini-1.0-pro']
        
        selected = None
        for kw in safe_keywords:
            for m in models:
                if kw in m and not any(bl in m for bl in blacklist):
                    selected = m
                    break
            if selected: break
            
        if selected:
            print(f"   [AI] 최신 SDK로 선택된 모델: {selected}")
            return selected
    except Exception as e:
        print(f"   [AI Model List Error] {e}")
        
    return "gemini-1.5-flash"

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
