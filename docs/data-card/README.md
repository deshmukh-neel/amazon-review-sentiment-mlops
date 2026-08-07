# ReviewSignal data card

## Production source

| Field | Value |
| --- | --- |
| Dataset | [`mteb/amazon_polarity`](https://huggingface.co/datasets/mteb/amazon_polarity) |
| Requested revision | `ec149c1` |
| Resolved revision | `ec149c1fe36043668a50804214d4597804001f6f` |
| Dataset version | `mteb-amazon_polarity-326981253e1a-s42` |
| Seed | `42` |
| Dataset-card license tag | Apache-2.0 |

The upstream dataset provides English review text and binary polarity labels with official train/test splits. ReviewSignal does not redistribute the source corpus. Ingestion resolves the abbreviated revision to the complete commit SHA, records SHA-256 values for every source data object, validates records, and writes private Parquet splits plus a `DataManifest`. The manifest also binds every materialized split to its own SHA-256, which training verifies before reading Parquet bytes.

## Deterministic splits

| Split | Source split | Rows | Negative | Positive |
| --- | --- | ---: | ---: | ---: |
| Train | Upstream train | 80,000 | 40,000 | 40,000 |
| Validation | Upstream train | 10,000 | 5,000 | 5,000 |
| Test | Upstream test | 10,000 | 5,000 | 5,000 |

The pipeline:

1. Rejects blank text and labels outside `{0, 1}`.
2. Normalizes whitespace and creates a normalized-text identity used for deduplication.
3. Deduplicates within and across source splits.
4. Samples each class deterministically with seed `42`.
5. Keeps validation disjoint from training and test disjoint from both.
6. Writes exact row/class counts, split URIs/checksums, source checksums, revision, seed, and timestamp to the strict manifest.

The test split is excluded from model selection and used only for release reporting. Tests prove deterministic sampling, class balance, split isolation, deduplication, manifest rejection, and synthetic end-to-end reproducibility.

## Storage and access

- Git contains only [`tests/fixtures/tiny_reviews.jsonl`](../../tests/fixtures/tiny_reviews.jsonl), a tiny synthetic fixture written for testing.
- Raw Hugging Face downloads and materialized production splits are ignored by Git.
- Cloud data and data manifests use a private, versioned GCS bucket with public-access prevention.
- Versioned split objects expire after 365 days across live and archived generations; deletion protection and non-destructive bucket settings remain enabled.
- Model artifacts and manifests are stored separately from data, with different least-privilege identities.

## Historical source

The original MSDS project used McAuley Lab's [Amazon Reviews'23](https://amazon-reviews-2023.github.io/) Video Games review and metadata files. The cleaned notebooks and historical Composer DAG are retained for provenance, but this research corpus is neither redistributed nor used by the production path.

## Known limitations

- Rating-derived polarity can be noisy and does not represent every form of sentiment.
- The corpus is English and may not generalize to other languages, time periods, or product domains.
- Balanced evaluation does not reproduce every real product-review class distribution.
- Review text may contain personal details, stereotypes, abusive language, or other source-data biases.
- Deduplication reduces exact normalized-text overlap but does not detect semantic paraphrases.
- No v1 feedback collection means the project cannot measure real production drift.
