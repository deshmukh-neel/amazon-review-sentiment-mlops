# Data card

## Production source

- Dataset: `mteb/amazon_polarity`
- Pinned revision: `ec149c1` (resolved to a full commit SHA at ingestion)
- Published fields: binary integer `label`, English review `text`, and human-readable `label_text`
- Published license tag: Apache-2.0

The repository does not redistribute the source corpus. Ingestion records the source revision and file checksums, then writes private Parquet splits to GCS.

## Deterministic splits

Seed `42` is used to select unique, balanced examples:

| Split | Source split | Rows | Negative | Positive |
| --- | --- | ---: | ---: | ---: |
| Train | Upstream train | 80,000 | 40,000 | 40,000 |
| Validation | Upstream train | 10,000 | 5,000 | 5,000 |
| Test | Upstream test | 10,000 | 5,000 | 5,000 |

Rows with blank text, invalid labels, or duplicate normalized text are rejected. The test split is excluded from model selection and used only for release reporting.

## Historical source

The original MSDS project used the McAuley Lab Amazon Reviews'23 Video Games review and metadata files. Those notebooks and the Composer DAG are retained for provenance, but the research corpus is not redistributed or used by the public production path.

## Known limitations

- Rating-derived polarity can be noisy and does not represent all forms of sentiment.
- The corpus is English and may not generalize to other languages or domains.
- Balanced evaluation does not reproduce every real product-review class distribution.
- Review text can contain stereotypes, abusive language, or other source-data biases.

