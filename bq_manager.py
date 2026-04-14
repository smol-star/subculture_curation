import os
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPIError
from datetime import datetime, timezone

PROJECT_ID = "modular-sign-491913-u6"
DATASET_ID = "subculture"
TABLE_ID = "curation_data"

def get_bq_client():
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        raise ValueError("[BQ] GOOGLE_APPLICATION_CREDENTIALS 환경 변수가 설정되지 않았습니다.")
    if not os.path.exists(creds_path):
        raise FileNotFoundError(f"[BQ] 인증 파일을 찾을 수 없습니다: {creds_path}")
    # 프로젝트 ID를 명시적으로 지정
    return bigquery.Client(project=PROJECT_ID)

def get_existing_urls(limit=150):
    """중복 저장을 막기 위해 최근 저장된 URL 리스트를 가져옴"""
    client = get_bq_client()
    query = f"SELECT content_url FROM `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}` ORDER BY timestamp DESC LIMIT {limit}"
    try:
        results = client.query(query).to_dataframe()
        if results.empty:
            return set()
        return set(results['content_url'].tolist())
    except Exception as e:
        print(f"[BQ Archive Search Error] {e}")
        return set()

def init_subculture_dataset_and_table():
    client = get_bq_client()
    # 프로젝트 명시
    dataset_ref = bigquery.DatasetReference(PROJECT_ID, DATASET_ID)

    try:
        client.get_dataset(dataset_ref)
        print(f"[BQ] Dataset '{DATASET_ID}' 이미 존재합니다.")
    except Exception:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        client.create_dataset(dataset, timeout=30)
        print(f"[BQ] Dataset '{DATASET_ID}' 생성 완료.")

    table_ref = bigquery.TableReference(dataset_ref, TABLE_ID)
    schema = [
        bigquery.SchemaField("source_country", "STRING"),
        bigquery.SchemaField("platform", "STRING"),
        bigquery.SchemaField("title", "STRING"),
        bigquery.SchemaField("content_url", "STRING"),
        bigquery.SchemaField("timestamp", "TIMESTAMP"),
        bigquery.SchemaField("engagement_score", "INT64"),
        bigquery.SchemaField("translated_full_text", "STRING"),
        bigquery.SchemaField("ai_summary", "STRING"),
        bigquery.SchemaField("is_hot", "BOOLEAN"),
    ]

    try:
        client.get_table(table_ref)
        print(f"[BQ] Table '{TABLE_ID}' 이미 존재합니다.")
    except Exception:
        table = bigquery.Table(table_ref, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="timestamp"
        )
        client.create_table(table)
        print(f"[BQ] Table '{TABLE_ID}' 생성 완료.")

def insert_records(records):
    if not records:
        return True

    # 중복 필터링 (최근에 저장된 URL을 제외)
    existing_urls = get_existing_urls()
    new_records = [r for r in records if r.get('content_url') not in existing_urls]
    
    if not new_records:
        print(f"[BQ] 수집된 {len(records)}개의 기사가 모두 이미 저장된 데이터입니다. (중복 방지)")
        return True

    client = get_bq_client()
    table_id = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    
    # 무료 티어 전용: 배치 로드(Batch Load) 방식 사용 (스트리밍 인서트 제한 우회)
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
    )

    try:
        # insert_rows_json 대신 load_table_from_json 사용
        load_job = client.load_table_from_json(new_records, table_id, job_config=job_config)
        load_job.result()  # 잡 완료 대기
        print(f"[BQ] {len(new_records)}개 신규 레코드가 배치 로드(무료 티어 공식 지원 방식)로 저장되었습니다.")
        return True
    except Exception as e:
        print(f"[BQ Load Error] {e}")
        return False

if __name__ == "__main__":
    init_subculture_dataset_and_table()
