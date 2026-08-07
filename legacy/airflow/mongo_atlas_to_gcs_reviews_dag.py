from datetime import datetime
import json
import os
from pathlib import Path

from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.hooks.gcs import GCSHook
from pymongo import MongoClient


DB_NAME = "msds697_final_project"
COLLECTION_NAME = "reviews_with_meta_verified"
GCS_BUCKET = "msds697-group-project-bucket"
GCS_PREFIX = "training-data"
SAMPLES_PER_CLASS = 10000 

LOCAL_DIR = Path("/tmp/amazon_reviews_export")


def get_collection():
    """Return MongoDB collection using URI stored in Airflow Variable."""
    mongo_uri = Variable.get("mongo_atlas_uri")
    client = MongoClient(mongo_uri)
    return client[DB_NAME][COLLECTION_NAME]


def check_connection():
    coll = get_collection()
    count = coll.count_documents({})
    print(f"Connected to Atlas. Document count: {count}")


def extract_reviews(**context):
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)

    coll = get_collection()

    pipeline = [
        {
            "$match": {
                "text": {"$exists": True, "$ne": ""},
                "rating": {"$exists": True, "$ne": None},
            }
        },
        {
            "$project": {
                "_id": 0,
                "review_id": {"$toString": "$_id"},
                "asin": 1,
                "review_title": "$title",
                "review_text": "$text",
                "rating": 1,
                "verified_purchase": 1,
                "helpful_vote": 1,
                "timestamp": 1,
                "main_category": {"$arrayElemAt": ["$meta_data.main_category", 0]},
                "product_title": {"$arrayElemAt": ["$meta_data.title", 0]},
                "label": {
                    "$cond": [{"$gte": ["$rating", 4]}, 1, 0]
                }
            }
        },
        {
            "$facet": {
                "positives": [
                    {"$match": {"label": 1}},
                    {"$limit": SAMPLES_PER_CLASS}
                ],
                "negatives": [
                    {"$match": {"label": 0}},
                    {"$limit": SAMPLES_PER_CLASS}
                ],
            }
        },
        {
            "$project": {
                "combined": {"$concatArrays": ["$positives", "$negatives"]}
            }
        },
        {"$unwind": "$combined"},
        {"$replaceRoot": {"newRoot": "$combined"}},
    ]

    output_file = LOCAL_DIR / f"reviews_{context['ds_nodash']}.jsonl"

    cursor = coll.aggregate(pipeline, allowDiskUse=True)

    written = 0
    with open(output_file, "w", encoding="utf-8") as f:
        for doc in cursor:
            combined_text = f"{doc.get('review_title', '')} {doc.get('review_text', '')}".strip()

            row = {
                "review_id": doc.get("review_id"),
                "asin": doc.get("asin"),
                "text": combined_text,
                "rating": doc.get("rating"),
                "label": doc.get("label"),
                "verified_purchase": doc.get("verified_purchase"),
                "helpful_vote": doc.get("helpful_vote"),
                "timestamp": doc.get("timestamp"),
                "main_category": doc.get("main_category"),
                "product_title": doc.get("product_title"),
            }

            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            written += 1

    print(f"Wrote {written} rows to {output_file}")
    context["ti"].xcom_push(key="output_file", value=str(output_file))


def upload_to_gcs(**context):
    output_file = context["ti"].xcom_pull(task_ids="extract_reviews", key="output_file")
    if not output_file:
        raise ValueError("No output file found in XCom")

    hook = GCSHook(gcp_conn_id="google_cloud_default")
    object_name = f"{GCS_PREFIX}/{os.path.basename(output_file)}"
    hook.upload(
        bucket_name=GCS_BUCKET,
        object_name=object_name,
        filename=output_file,
    )

    print(f"Uploaded {output_file} to gs://{GCS_BUCKET}/{object_name}")


with DAG(
    dag_id="mongo_atlas_to_gcs_reviews",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["mongo", "atlas", "gcs", "ml"],
) as dag:

    t1 = PythonOperator(
        task_id="check_connection",
        python_callable=check_connection,
    )

    t2 = PythonOperator(
        task_id="extract_reviews",
        python_callable=extract_reviews,
    )

    t3 = PythonOperator(
        task_id="upload_to_gcs",
        python_callable=upload_to_gcs,
    )

    t1 >> t2 >> t3
