# ReviewSignal: Amazon Review Sentiment MLOps

ReviewSignal turns an MSDS Amazon-reviews class project into a reproducible, production-shaped machine-learning system. It validates and versions sentiment data, trains and gates a classical NLP model, serves predictions through FastAPI, and deploys a scale-to-zero web demo and scheduled training job on Google Cloud.

The production implementation is being built in five verified milestones. The original MongoDB Atlas, Cloud Composer, and PySpark work remains available under `legacy/`, `notebooks/`, and `docs/assets/` as project-evolution evidence.

## Project Contents

| Path | Purpose |
| --- | --- |
| `src/reviewsignal/` | Production ingestion, training, artifact, API, and web-demo code. |
| `tests/` | Unit, API, and end-to-end synthetic-data verification. |
| `infra/terraform/` | GCP infrastructure-as-code for Cloud Run, GCS, Scheduler, IAM, and monitoring. |
| `legacy/airflow/` | Original MongoDB Atlas to GCS Cloud Composer DAG. |
| `notebooks/` | Cleaned historical MongoDB/PySpark exploration notebooks. |
| `docs/assets/` | Cropped historical cloud screenshots. |

Large data exports, generated Parquet splits, and trained models are intentionally excluded from Git. Production artifacts live in private GCS buckets; tests use a tiny synthetic fixture.

## Historical data pipeline

1. Amazon reviews and product metadata are joined in MongoDB using `parent_asin`.
2. The joined collection is filtered to verified purchases and stored as `reviews_with_meta_verified`.
3. The Airflow DAG reads from MongoDB Atlas and keeps records with non-empty review text and a rating.
4. Labels are derived from ratings:
   - `1` for ratings greater than or equal to 4
   - `0` for ratings less than 4
5. The DAG samples up to 10,000 positive and 10,000 negative reviews per run.
6. The output is uploaded to:

```text
gs://msds697-group-project-bucket/training-data/reviews_<YYYYMMDD>.jsonl
```

## Local setup

Install Python 3.11 and [uv](https://docs.astral.sh/uv/), then synchronize the locked environment:

```bash
uv sync
uv run pytest
```

The production CLI will expose these commands:

```bash
uv run reviewsignal ingest
uv run reviewsignal train
uv run reviewsignal evaluate
uv run reviewsignal pipeline
```

Run the web application locally after a model has been trained:

```bash
uv run uvicorn reviewsignal.api:app --reload
```

Open `http://127.0.0.1:8000` for the demo or `/docs` for OpenAPI.

## Original Cloud Composer pipeline

To run the export workflow in Cloud Composer:

1. Upload `legacy/airflow/mongo_atlas_to_gcs_reviews_dag.py` to the Composer DAGs folder.
2. Create an Airflow Variable named `mongo_atlas_uri` containing the MongoDB Atlas connection URI.
3. Ensure the `google_cloud_default` Airflow connection can write to `msds697-group-project-bucket`.
4. Trigger the `mongo_atlas_to_gcs_reviews` DAG or wait for the daily schedule.

The DAG runs three tasks in order:

```text
check_connection -> extract_reviews -> upload_to_gcs
```

## Dataset and modeling notes

The historical notebook builds binary classifiers with Spark ML. The production pipeline uses the Apache-2.0-tagged `mteb/amazon_polarity` dataset revision `ec149c1`, deterministic train/validation/test splits, and TF-IDF plus logistic regression for fast, interpretable inference.

- The initial promotion gate requires validation macro-F1 of at least 0.85.
- A candidate must beat a stratified dummy baseline by at least 0.15 macro-F1.
- Later candidates may not regress by more than 0.01 macro-F1 from production.
- Submitted demo text is never persisted or logged.

See `docs/data-card/`, `docs/model-card/`, and `docs/architecture/` for lineage, limitations, and deployment details.

## License and attribution

Project code is MIT licensed. Dataset terms remain separate. The original class project used [Amazon Reviews'23](https://amazon-reviews-2023.github.io/) from McAuley Lab; the production path uses [`mteb/amazon_polarity`](https://huggingface.co/datasets/mteb/amazon_polarity), whose dataset card identifies Apache-2.0 terms. Raw datasets are not redistributed here.
