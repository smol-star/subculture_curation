import streamlit as st
from google.cloud import bigquery
import pandas as pd
import json
import os
from datetime import datetime

st.set_page_config(page_title="🎬 서브컬처 쇼츠 기획 센터", page_icon="🎬", layout="wide")

st.markdown("""
    <style>
    .nav-header { font-size: 2.5em; font-weight: bold; color: #ff4b4b; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# ─── BQ 클라이언트 ───
@st.cache_resource
def get_bq_client():
    if "gcp_service_account" in st.secrets:
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_info(st.secrets["gcp_service_account"])
        return bigquery.Client(credentials=creds, project=creds.project_id)
    return bigquery.Client()

@st.cache_data(ttl=600)
def load_bq_data():
    client = get_bq_client()
    query = """
        SELECT * FROM `modular-sign-491913-u6.subculture.curation_data`
        WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 3 DAY)
        ORDER BY timestamp DESC
        LIMIT 100
    """
    import db_dtypes
    return client.query(query).to_dataframe()

# ─── 아카이브 렌더 함수 ───
def render_list(df):
    if df is None or (hasattr(df, 'empty') and df.empty) or (isinstance(df, list) and not df):
        st.info("수집된 데이터가 없습니다.")
        return

    # DataFrame이면 리스트로 변환
    if hasattr(df, 'to_dict'):
        records = df.to_dict('records')
    else:
        records = df

    hot_items = [r for r in records if r.get('is_hot')]
    if hot_items:
        st.subheader("🔥 쇼츠 추천 핫이슈")
        cols = st.columns(min(len(hot_items), 3))
        for i, row in enumerate(hot_items[:3]):
            with cols[i]:
                st.markdown(f"**[{row.get('platform','?')}]**")
                st.info(str(row.get('title', ''))[:40] + "...")
                if st.button("대본 보기", key=f"hot_{i}_{row.get('content_url','')}"):
                    st.session_state['selected_item'] = row
        st.divider()

    col_l, col_r = st.columns([1, 1.5])
    with col_l:
        st.subheader("📅 수집 리스트")
        for i, row in enumerate(records):
            hot_label = "🔥 " if row.get('is_hot') else ""
            label = f"{hot_label}[{row.get('platform','?')}] {str(row.get('title',''))[:35]}"
            if st.button(label, key=f"list_{i}_{row.get('content_url','')}", use_container_width=True):
                st.session_state['selected_item'] = row

    with col_r:
        if 'selected_item' in st.session_state:
            item = st.session_state['selected_item']
            st.subheader("📄 상세 큐레이션 결과")
            st.markdown(f"### {item.get('title','')}")
            st.caption(f"📍 {item.get('platform','?')} | 📅 {item.get('timestamp','?')} | 🌍 {item.get('source_country','?')}")
            st.success("📝 **유튜브 쇼츠 나레이션 대본**")
            st.write(item.get('ai_summary', '대본 없음'))
            with st.expander("🔍 원문 전체 통번역 보기 (팩트체크)"):
                st.write(item.get('translated_full_text', '번역 정보 없음'))
            st.markdown(f"[🔗 원문 링크 열기]({item.get('content_url','#')})")
        else:
            st.info("왼쪽 목록에서 항목을 선택하면 대본과 번역을 확인할 수 있습니다.")

# ─── 사이드바 메뉴 ───
st.markdown('<div class="nav-header">🎬 서브컬처 쇼츠 기획 센터</div>', unsafe_allow_html=True)
page = st.sidebar.radio("메뉴", ["실시간 큐레이션", "과거 기록 보기"])

if page == "실시간 큐레이션":
    st.write("글로벌 서브컬처 RSS를 AI로 큐레이션한 쇼츠 대본 기획 대시보드입니다.")
    try:
        df = load_bq_data()
        render_list(df)
    except Exception as e:
        st.error(f"BigQuery 데이터 로드 실패: {e}")
        st.info("💡 GitHub Actions에서 파이프라인을 1회 수동 실행하여 데이터를 수집해주세요.")

else:
    st.title("📜 과거 서브컬처 기록 보관소")
    st.write("3시간마다 수집되어 저장된 과거 기록 스냅샷을 열람할 수 있습니다.")
    
    archive_dir = "hourly_archive"
    if not os.path.exists(archive_dir):
        st.warning("🗂️ 아직 저장된 과거 기록이 없습니다. 파이프라인을 최소 1회 실행해주세요.")
    else:
        dates = sorted([d for d in os.listdir(archive_dir) if os.path.isdir(os.path.join(archive_dir, d))], reverse=True)
        if not dates:
            st.warning("🗂️ 아직 날짜별 기록이 없습니다.")
        else:
            def fmt_date(d):
                try:
                    dt = datetime.strptime(d, "%Y-%m-%d")
                    days = ["월", "화", "수", "목", "금", "토", "일"]
                    return f"{d} ({days[dt.weekday()]})"
                except:
                    return d
            
            col1, col2 = st.columns(2)
            with col1:
                selected_date = st.selectbox("📅 날짜 선택", dates, format_func=fmt_date)
            
            date_dir = os.path.join(archive_dir, selected_date)
            hour_files = sorted([f.replace('.json','') for f in os.listdir(date_dir) if f.endswith('.json')], reverse=True)
            
            with col2:
                if not hour_files:
                    st.selectbox("⏰ 시간 선택", ["기록 없음"])
                    selected_hour = None
                else:
                    selected_hour = st.selectbox("⏰ 시간 선택", hour_files, format_func=lambda x: f"{x}시 스냅샷")
            
            if hour_files and selected_hour:
                file_path = os.path.join(date_dir, f"{selected_hour}.json")
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        archive_data = json.load(f)
                    st.success(f"✅ {fmt_date(selected_date)} {selected_hour}시 스냅샷")
                    render_list(archive_data)
                except Exception as e:
                    st.error(f"파일 읽기 실패: {e}")
