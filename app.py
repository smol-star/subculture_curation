import streamlit as st
from google.cloud import bigquery
import pandas as pd
import json
import os
from dotenv import load_dotenv

load_dotenv()

# 페이지 설정
st.set_page_config(page_title="Subculture Shorts Curator", page_icon="🎬", layout="wide")

# 스타일링 (매거진 감성 다크모드)
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #ffffff; }
    .stCard { border: 1px solid #30363d; border-radius: 10px; padding: 20px; background-color: #161b22; margin-bottom: 20px; }
    .hot-badge { background-color: #ff4b4b; color: white; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.8em; }
    .nav-header { font-size: 2.5em; font-weight: bold; color: #ff4b4b; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=600)
def load_data():
    # Streamlit Cloud 환경에서 구글 인증 처리
    # (로컬 .env 에서는 GOOGLE_APPLICATION_CREDENTIALS 사용)
    if "gcp_service_account" in st.secrets:
        # Streamlit secrets TOML 방식으로 연결
        from google.oauth2 import service_account
        credentials = service_account.Credentials.from_service_account_info(st.secrets["gcp_service_account"])
        client = bigquery.Client(credentials=credentials, project=credentials.project_id)
    else:
        # 로컬 환경
        client = bigquery.Client()
        
    query = """
        SELECT * FROM `subculture.curation_data` 
        ORDER BY timestamp DESC 
        LIMIT 50
    """
    return client.query(query).to_dataframe()

st.markdown('<div class="nav-header">🎬 서브컬처 쇼츠 기획 센터</div>', unsafe_allow_html=True)
st.write("실시간 글로벌 서브컬처 정보를 분석하여 쇼츠 대본 초안을 제공합니다.")

try:
    df = load_data()
    
    # 상단 핫 토픽 섹션
    hot_df = df[df['is_hot'] == True].head(5)
    if not hot_df.empty:
        st.subheader("🔥 오늘의 쇼츠 추천 (Hot Topics)")
        cols = st.columns(len(hot_df))
        for i, (idx, row) in enumerate(hot_df.iterrows()):
            with cols[i]:
                st.markdown(f"**[{row['platform']}]**")
                st.info(row['title'][:30] + "...")
                if st.button("대본 보기", key=f"hot_{i}"):
                    st.session_state['selected_item'] = row

    st.divider()

    # 전체 리스트 섹션
    col_l, col_r = st.columns([1, 1.5])
    
    with col_l:
        st.subheader("📅 최근 수집 리스트")
        for idx, row in df.iterrows():
            hot_label = "🔥 " if row['is_hot'] else ""
            if st.button(f"{hot_label}[{row['platform']}] {row['title'][:40]}", key=f"list_{idx}", use_container_width=True):
                st.session_state['selected_item'] = row

    with col_r:
        if 'selected_item' in st.session_state:
            item = st.session_state['selected_item']
            st.subheader("📄 상세 큐레이션 결과")
            
            with st.container():
                st.markdown(f"### {item['title']}")
                st.caption(f"📍 {item['platform']} | 📅 {item['timestamp']} | 🌍 {item['source_country']}")
                
                # 쇼츠 대본 영역
                st.success("📝 **유튜브 쇼츠 나레이션 대본**")
                st.write(item['ai_summary'])
                
                # 원문 통번역 (펼치기 형식)
                with st.expander("🔍 원문 전체 통번역 보기 (팩트체크)"):
                    st.write(item.get('translated_full_text', '번역 정보 없음'))
                
                st.markdown(f"[🔗 원문 링크 열기]({item['content_url']})")
        else:
            st.info("왼쪽 리스트에서 메뉴를 선택하면 대본과 상세 번역을 확인할 수 있습니다.")

except Exception as e:
    st.error(f"데이터 로드 실패: {e}")
    st.info("💡 처음 실행하셨나요? 서버에서 정보 수집을 먼저 실행하거나, 구글 클라우드 보안키(.json) 연동이 필요합니다.")
