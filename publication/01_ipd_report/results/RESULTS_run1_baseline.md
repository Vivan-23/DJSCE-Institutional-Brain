# Evaluation results — 2026-10-13 04:45 UTC

Model: `openai/gpt-oss-120b` · laya: `0.3.21` · dataset: synthetic (see `evaluation/data/`).
Regenerate with `evaluation/run_eval.ps1`; numbers vary slightly between runs because LLM outputs vary.

## 1. Help-desk triage (96 labelled queries, 6 categories)

| Engine | Coverage | Accuracy | Macro-F1 | Urgency F1 | p50 latency (s) | p95 latency (s) |
|---|---|---|---|---|---|---|
| keyword | 100% | 57.3% | 0.586 | 0.533 | 0.0 | 0.0 |
| llm | 100% | 90.6% | 0.907 | 1.000 | 2.637 | 2.816 |
| laya | 67% | 51.0% | 0.563 | 0.533 | 1.406 | 1.815 |
| llm→keyword | 100% | 90.6% | 0.907 | 1.000 | 2.637 | 2.816 |
| laya→keyword | 100% | 68.8% | 0.684 | 0.533 | 1.406 | 1.815 |
| laya→llm→keyword | 100% | 81.2% | 0.805 | 0.625 | 1.596 | 4.102 |

Engines alone count an abstention as wrong; chains fall back to the keyword classifier.

## 2. Grounded question answering (24 questions)

| Asked as | n | Retrieval hit@5 | Answer correct | Cited | Abstained | p50 (s) | p95 (s) |
|---|---|---|---|---|---|---|---|
| student | 12 | 100% | 75% | 75% | 17% | 1.104 | 2.517 |
| staff | 12 | 100% | 67% | 100% | 0% | 5.083 | 8.013 |
| overall | 24 | 100% | 71% | 88% | 8% | 4.206 | 8.215 |

## 3. Visibility (adversarial student queries)

**0 leaks in 20 queries** — 0 returned an internal source, 0 stated an internal-only fact; every query scoped to public: True.

## 4. Commitment extraction (4 transcripts, hand-labelled)

Gold 9 · extracted 9 · matched 9 → **precision 100%, recall 100%, F1 1.00**.

