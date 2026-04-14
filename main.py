from datetime import datetime
import rss_fetcher
import ai_processor
import bq_manager

def run_pipeline():
    print("=" * 60)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 서브컬처 큐레이션 파이프라인 시작")
    print("=" * 60)
    
    # 1. BQ 스키마 검증/초기화 (선택적)
    bq_manager.init_subculture_dataset_and_table()

    # 2. 무료 RSS 및 뉴스 크롤링으로 정보 수집
    print("\n[Step 1] RSS / 뉴스 데이터 스크래핑 중...")
    raw_data = rss_fetcher.fetch_rss_sources(limit_per_source=10)
    
    if not raw_data:
        print("수집된 데이터가 없습니다. 파이프라인 종료.")
        return
        
    # 3. Gemini Pro를 활용한 대본 가공 및 플래그 세팅
    print("\n[Step 2] Gemini Pro (High) 큐레이션 진행 중...")
    curated_data = ai_processor.curate_and_generate_scripts(raw_data)
    
    # raw_text 필드는 BQ 스키마에 제외되어 있으므로(또는 너무 길수 있으므로) 삭제
    for item in curated_data:
        if "raw_text" in item:
            del item["raw_text"]
            
    # 추천/필터링 통계
    hot_count = sum(1 for x in curated_data if x.get("is_hot"))
    print(f"-> 총 {len(curated_data)}건 중 쇼츠 제작용(핫이슈)으로 {hot_count}건 선정됨.")
    
    # 4. BigQuery 적재
    print("\n[Step 3] Google BigQuery 에 데이터 적재 중...")
    success = bq_manager.insert_records(curated_data)
    
    if success:
        print("\n🎉 모든 파이프라인(Task 1)이 정상적으로 완료되었습니다!")
    else:
        print("\n⚠️ 파이프라인 완료 중 오류가 발생했습니다.")

if __name__ == "__main__":
    run_pipeline()
