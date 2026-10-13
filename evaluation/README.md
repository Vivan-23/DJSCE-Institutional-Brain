# Evaluation harness

Produces every number the report and poster quote. Results are written to
[`publication/01_ipd_report/results/`](../publication/01_ipd_report/results/)
(`RESULTS.md`, `latest.json`, one timestamped JSON per run).

## Run it

The stack must be up with the synthetic dataset loaded:

```bash
docker compose up -d --build
python ingest_institutional.py --approve
docker compose --profile eval run --rm evaluator          # all four parts
```

Or on Windows: `./evaluation/run_eval.ps1`.

The `evaluator` service reuses the backend image, installs the optional
`laya==0.3.21` classifier only inside itself, and caches Hugging Face downloads in the
`hf-cache` volume. The first run downloads laya's checkpoint, about 4 minutes.

Run one part with a custom command, for example:

```bash
docker compose --profile eval run --rm evaluator "pip install --user --no-deps -q laya==0.3.21 && python /eval/run_eval.py --parts triage --engines keyword,laya"
```

## What it measures

| Part | Data | Metrics |
|---|---|---|
| `triage` | `data/triage_set.jsonl`: 96 student queries, 6 categories, urgency labels | coverage, accuracy, macro-F1, urgency F1, p50/p95 latency per engine (keyword, LLM, laya) and per fallback chain |
| `qa` | `data/qa_set.json`: 12 student + 12 staff questions with gold sources and answer keywords | retrieval hit@5, answer correct, cited, abstained, latency |
| `visibility` | `data/visibility_set.json`: 20 adversarial student questions about internal content | leaks (internal source returned or internal-only fact stated); target 0 |
| `commitments` | `data/commitments_gold.json`: hand-labelled "I will …" commitments in the 4 transcripts | precision, recall, F1 |

## Limitations to state in the report

- All data, including the gold labels, is synthetic and written by the project team, so
  results show the system works as designed. They are not a field study.
- "Answer correct" is a keyword check against gold facts; it does not judge fluency.
- LLM outputs vary between runs. Report the run date and model from `RESULTS.md`, and
  rerun before submission.
- laya 0.3.21 is a very young package (first PyPI release 18 Sep 2026), so it is used
  only here and as an opt-in engine, never as a required dependency.
