import os
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPIError
from datetime import datetime, timezone

# GCP Credentials from ENV or User settings
# Expected to have GOOGLE_APPLICATION_CREDENTIALS set

DATASET_ID = "subculture"
TABLE_ID = "curation_data"

def get_bq_client():
    return bigquery.Client()

def init_subculture_dataset_and_table():
    client = get_bq_client()
    dataset_ref = client.dataset(DATASET_ID)
    
    try:
        client.get_dataset(dataset_ref)
        print(f"[BQ] Dataset '{DATASET_ID}' 이미 존재합니다.")
    except Exception:
        # Create dataset
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        dataset = client.create_dataset(dataset, timeout=30)
        print(f"[BQ] Dataset '{DATASET_ID}' 생성 완료.")

    table_ref = dataset_ref.table(TABLE_ID)
    schema = [
        bigquery.SchemaField("source_country", "STRING", description="국가 (미국, 일본, 한국, 중국)"),
        bigquery.SchemaField("platform", "STRING", description="사이트명 (Reddit, Famitsu 등)"),
        bigquery.SchemaField("title", "STRING", description="원문 제목"),
        bigquery.SchemaField("content_url", "STRING", description="글/뉴스 원문 링크"),
        bigquery.SchemaField("timestamp", "TIMESTAMP", description="수집 시간"),
        bigquery.SchemaField("engagement_score", "INT64", description="추천수, 조회수 등 트렌드 지표"),
        bigquery.SchemaField("translated_full_text", "STRING", description="원문 전체의 한국어 통번역본 (팩트체크용)"),
        bigquery.SchemaField("ai_summary", "STRING", description="Gemini API가 요약 및 번역한 쇼츠용 대본 초안"),
        bigquery.SchemaField("is_hot", "BOOLEAN", description="트렌드 여부 플래그 (쇼츠 제작 가치)")
    ]

    try:
        client.get_table(table_ref)
        print(f"[BQ] Table '{TABLE_ID}' 이미 존재합니다.")
    except Exception:
        table = bigquery.Table(table_ref, schema=schema)
        # 파티셔닝 적용 (무료 스캔 최적화)
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="timestamp"
        )
        table = client.create_table(table)
        print(f"[BQ] Table '{TABLE_ID}' 생성 완료.")

def insert_records(records):
    """
    records: list of dict matches the BQ schema.
    Returns: bool (Success)
    """
    if not records:
        return True

    client = get_bq_client()
    table_ref = client.dataset(DATASET_ID).table(TABLE_ID)
    
    try:
        errors = client.insert_rows_json(table_ref, records)
        if errors == []:
            print(f"[BQ] {len(records)}개의 서브컬처 레코드 저장 성공.")
            return True
        else:
            print(f"[BQ Insert Error] {errors}")
            return False
    except GoogleAPIError as e:
        print(f"[BQ API Error] {e}")
        return False

if __name__ == "__main__":
    init_subculture_dataset_and_table()
