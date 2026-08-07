# ReviewSignal model card

## Model details

| Field | Value |
| --- | --- |
| Model version | `20260807T201536Z-9348d52` |
| Dataset version | `mteb-amazon_polarity-326981253e1a-s42` |
| Training Git SHA | `9348d523dacb6fda52c42772070cc074de20c2f8` |
| Trained | 2026-08-07 20:15:36 UTC |
| Artifact SHA-256 | `15b9f85c779833a2fe06dfac3bdbb033f376dc9f1f9f07073a8ac3eb3961039b` |
| Artifact size | 990,318 bytes (about 968 KiB) |

The estimator is one scikit-learn pipeline:

1. Word TF-IDF with unigrams and bigrams, `max_features=50_000`, `min_df=2`, and `sublinear_tf=True`.
2. Logistic regression with `C=1.0`, `max_iter=1000`, and `random_state=42`.

Recorded runtime versions are Python 3.11.15, scikit-learn 1.9.0, pandas 2.3.3, and joblib 1.5.3. The service verifies the artifact SHA-256 before deserializing it.

## Intended use

ReviewSignal demonstrates a reproducible binary sentiment-classification lifecycle for portfolio review and low-stakes experimentation. It predicts whether a 1–5,000-character English product review is positive or negative and reports the positive-class model probability.

It is not intended for automated moderation, employee/customer assessment, safety decisions, medical or legal use, or any workflow where an incorrect sentiment label could materially affect a person.

## Evaluation data

Evaluation uses deterministic, balanced, deduplicated splits from the pinned `mteb/amazon_polarity` revision. Validation contains 10,000 records from the upstream training split. The held-out test contains 10,000 records from the upstream test split and is excluded from model selection.

## Results

| Metric | Validation | Test |
| --- | ---: | ---: |
| Accuracy | 0.9155 | 0.9153 |
| Macro F1 | 0.9155 | 0.9153 |
| Positive precision | 0.9174 | 0.9162 |
| Positive recall | 0.9132 | 0.9142 |
| ROC-AUC | 0.9716 | 0.9729 |
| Dummy macro F1 | 0.3333 | 0.3333 |
| Macro-F1 improvement | 0.5822 | 0.5820 |
| Model-only latency¹ | 0.27 ms | 0.27 ms |

Validation confusion matrix (`[[TN, FP], [FN, TP]]`):

```text
[[4589, 411],
 [ 434, 4566]]
```

Test confusion matrix:

```text
[[4582, 418],
 [ 429, 4571]]
```

¹ Average single-record `predict_proba` time over 25 repetitions on local Apple Silicon. This is not an end-to-end Cloud Run latency measurement.

The machine-readable values are in [`docs/metrics/v1-candidate-metrics.json`](../metrics/v1-candidate-metrics.json).

## Promotion policy

- Initial validation macro-F1 must be at least `0.85`.
- Validation macro-F1 must exceed the most-frequent dummy baseline by at least `0.15`.
- A replacement may not regress by more than `0.01` from the current production validation macro-F1.
- The candidate manifest must parse strictly, and its artifact checksum must match before evaluation or serving.
- Passing metrics creates no production traffic by itself; promotion remains an explicit protected workflow.

This candidate passes the initial gates: validation macro-F1 is `0.9155`, and its improvement over dummy is `0.5822`.

## Limitations and ethical considerations

- The returned number is a model probability, not a guarantee or a human-calibrated measure of confidence.
- The task is binary and cannot express neutral, mixed, or aspect-level sentiment.
- Training data is English product-review text; behavior may degrade on other languages and domains.
- Sarcasm, negation, misspellings, dialect, coded language, and adversarial wording can cause errors.
- Rating-derived labels can be noisy and may encode source-platform and reviewer biases.
- Balanced evaluation does not reproduce every real deployment's class distribution.
- Review text can contain abusive or stereotyped language inherited from the source corpus.
- No submitted text or user feedback is retained, so v1 does not claim production drift detection.

## Privacy

The API logs request IDs, route, status, latency, and model version only. It never writes submitted review text to application logs or storage. This policy is covered by API tests.
