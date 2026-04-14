from datetime import datetime, timezone, timedelta
import os
import json
import rss_fetcher
import ai_processor
import bq_manager

def save_archive(data):
    """수집 결과를 hourly_archive/YYYY-MM-DD/HH.json 에 저장"""
    try:
        kst = timezone(timedelta(hours=9))
        now_kst = datetime.now(kst)
        date_str = now_kst.strftime("%Y-%m-%d")
        hour_str = now_kst.strftime("%H")
        
        archive_dir = os.path.join("hourly_archive", date_str)
        os.makedirs(archive_dir, exist_ok=True)
        
        archive_path = os.path.join(archive_dir, f"{hour_str}.json")
        with open(archive_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  [Archive] {len(data)}건 스냅샷 저장 완료: {archive_path}")
    except Exception as e:
        print(f"  [Archive] 저장 실패: {e}")

def run_pipeline():
    print("=" * 65)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔥 서브컬처 파이프라인 가동")
    print("=" * 65)
    
    # 1. BQ 스키마 검증/초기화
    bq_manager.init_subculture_dataset_and_table()

    # 2. RSS 수집
    print(f"\n[Step 1] RSS 데이터 수집 단계")
    raw_data = rss_fetcher.fetch_rss_sources(limit_per_source=8)
    print(f"▶ [결과] 총 {len(raw_data)}건의 원본 데이터를 확보했습니다.")
    
    if not raw_data:
        print("❌ 수집된 데이터가 0건입니다. 파이프라인을 종료합니다.")
        return
        
    # 3. AI 큐레이션
    print(f"\n[Step 2] AI 큐레이션 및 대본 가공 단계")
    curated_data = ai_processor.curate_and_generate_scripts(raw_data)
    
    for item in curated_data:
        item.pop("raw_text", None)
            
    hot_count = sum(1 for x in curated_data if x.get("is_hot"))
    print(f"▶ [결과] AI 처리가 완료되었습니다. (총 {len(curated_data)}건 중 핫이슈 {hot_count}건 선정)")
    
    # 4. 로컬 아카이브 저장
    print(f"\n[Step 3] 로컬 아카이브(JSON) 파일 저장 중...")
    save_archive(curated_data)
    
    # 5. BigQuery 적재
    print(f"\n[Step 4] BigQuery 최종 적재 단계")
    print(f"▶ 데이터 적재 시도 중... (대상: {len(curated_data)}건)")
    success = bq_manager.insert_records(curated_data)
    
    if success:
        print("\n" + "★" * 30)
        print("🎉 모든 파이프라인이 성공적으로 완료되었습니다!")
        print("★" * 30)
    else:
        print("\n⚠️ BigQuery 적재 중 오류가 보고되었습니다. (위 로그를 확인하세요)")

if __name__ == "__main__":
    run_pipeline()
