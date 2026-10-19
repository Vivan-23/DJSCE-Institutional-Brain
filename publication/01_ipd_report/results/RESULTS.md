# Evaluation results — 2026-10-19 14:55 UTC

Model: `openai/gpt-oss-120b` · laya: `0.3.21` · dataset: synthetic (see `evaluation/data/`).
Regenerate with `evaluation/run_eval.ps1`; numbers vary slightly between runs because LLM outputs vary.

## 1. Help-desk triage (96 labelled queries, 6 categories)

| Engine | Coverage | Accuracy | Macro-F1 | Urgency F1 | p50 latency (s) | p95 latency (s) |
|---|---|---|---|---|---|---|
| keyword | 100% | 57.3% | 0.586 | 0.533 | 0.0 | 0.0 |
| llm | 100% | 90.6% | 0.907 | 1.000 | 2.489 | 4.53 |
| laya | 67% | 51.0% | 0.563 | 0.533 | 1.387 | 1.923 |
| llm→keyword | 100% | 90.6% | 0.907 | 1.000 | 2.489 | 4.53 |
| laya→keyword | 100% | 68.8% | 0.684 | 0.533 | 1.387 | 1.923 |
| laya→llm→keyword | 100% | 80.2% | 0.794 | 0.625 | 1.537 | 4.466 |

Engines alone count an abstention as wrong; chains fall back to the keyword classifier.

## 2. Grounded question answering (33 questions)

| Asked as | n | Retrieval hit@5 | Answer correct | Cited | Abstained | p50 (s) | p95 (s) |
|---|---|---|---|---|---|---|---|
| student | 21 | 100% | 90% | 100% | 0% | 3.249 | 7.84 |
| staff | 12 | 100% | 92% | 92% | 0% | 8.8 | 10.111 |
| overall | 33 | 100% | 91% | 97% | 0% | 6.725 | 10.031 |

## 3. Visibility (adversarial student queries)

**0 leaks in 20 queries** — 0 returned an internal source, 0 stated an internal-only fact; every query scoped to public: True.

## 3b. Department isolation (students asking about other departments)

**0 leaks in 10 queries** — a leak is any source from a department outside the student's own department plus institution-wide material.

## 4. Commitment extraction (4 transcripts, hand-labelled)

Gold 9 · extracted 9 · matched 9 → **precision 100%, recall 100%, F1 1.00**.

