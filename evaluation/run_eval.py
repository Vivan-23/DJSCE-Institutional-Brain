"""
Evaluation harness for DJSCE Institutional Brain.

Measures, on the synthetic dataset, the four claims the report makes:
  1. triage   — help-desk category/urgency accuracy, macro-F1 and latency per engine
                (keyword baseline, LLM, laya) and per deployed chain;
  2. qa       — grounded answers: retrieval hit@5, answer correctness, citation rate, latency;
  3. visibility — adversarial student queries: leaks of internal evidence (target 0);
  4. commitments — extraction precision/recall against hand-labelled gold.

Runs inside the backend image (see evaluation/README.md). Triage calls the service
directly; the other parts go through the live HTTP API as real users. Writes
results/<timestamp>.json and results/RESULTS.md (+ latest.json) into --out.
"""
import argparse
import json
import os
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CITE_RE = re.compile(r"\[\d+\]|【\d+[^】]*】")
ABSTAIN_RE = re.compile(r"(does not|doesn't|do not) (contain|include|mention|provide)|not (in|available in) the (provided )?(context|documents)|no information", re.I)


# ── helpers ──────────────────────────────────────────────────────────────────
_SPACES = dict.fromkeys(map(ord, "      "), " ")
_DASHES = dict.fromkeys(map(ord, "‐‑‒–—"), "-")


def norm(text):
    """Lower-case with Unicode spaces/dashes folded, so 'October 14' matches 'October 14'."""
    return (text or "").translate(_SPACES).translate(_DASHES).lower()


def pct(xs, p):
    if not xs:
        return None
    xs = sorted(xs)
    k = min(len(xs) - 1, max(0, round(p / 100 * (len(xs) - 1))))
    return round(xs[k], 3)


def macro_f1(gold, pred, labels):
    f1s = []
    for lab in labels:
        tp = sum(1 for g, p in zip(gold, pred) if g == lab and p == lab)
        fp = sum(1 for g, p in zip(gold, pred) if g != lab and p == lab)
        fn = sum(1 for g, p in zip(gold, pred) if g == lab and p != lab)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    return round(sum(f1s) / len(f1s), 3)


def binary_f1(gold, pred):
    tp = sum(1 for g, p in zip(gold, pred) if g and p)
    fp = sum(1 for g, p in zip(gold, pred) if not g and p)
    fn = sum(1 for g, p in zip(gold, pred) if g and not p)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return round(2 * prec * rec / (prec + rec), 3) if prec + rec else 0.0


class Api:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self._tokens = {}

    def token(self, email):
        if email not in self._tokens:
            r = requests.post(f"{self.base}/api/v1/auth/login", json={"email": email, "password": "demo123"}, timeout=30)
            r.raise_for_status()
            self._tokens[email] = r.json()["access_token"]
        return {"Authorization": f"Bearer {self._tokens[email]}"}

    def chat(self, email, question):
        t = time.perf_counter()
        r = requests.post(
            f"{self.base}/api/v1/chat",
            json={"messages": [{"role": "user", "content": question}]},
            headers=self.token(email),
            timeout=180,
        )
        dt = time.perf_counter() - t
        r.raise_for_status()
        return r.json(), dt

    def get(self, email, path):
        r = requests.get(f"{self.base}{path}", headers=self.token(email), timeout=60)
        r.raise_for_status()
        return r.json()


# ── 1. triage ────────────────────────────────────────────────────────────────
def eval_triage(engines, pause):
    from app.core.institution_config import get_institution_config
    from app.services.ticket_service import ticket_service

    labels = [c.key for c in get_institution_config().helpdesk_categories]
    items = [json.loads(line) for line in (DATA / "triage_set.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    calls = {"keyword": ticket_service.keyword_triage, "llm": ticket_service.llm_triage, "laya": ticket_service.laya_triage}

    raw = {}  # engine -> list of (result or None, seconds)
    for eng in engines:
        if eng == "laya":
            try:
                ticket_service.laya_triage("warm-up: load the laya checkpoint")
            except Exception as e:  # noqa: BLE001
                print(f"[triage] laya unavailable: {e}", file=sys.stderr)
                continue
        out = []
        for it in items:
            t = time.perf_counter()
            try:
                res = calls[eng](it["text"])
            except Exception as e:  # noqa: BLE001
                print(f"[triage] {eng} failed on {it['id']}: {e}", file=sys.stderr)
                res = None
            out.append((res, time.perf_counter() - t))
            if eng == "llm" and pause:
                time.sleep(pause)
        raw[eng] = out
        print(f"[triage] {eng}: done", file=sys.stderr)

    def score(preds, lat):
        gold_c = [it["category"] for it in items]
        gold_u = [it["urgent"] for it in items]
        pred_c = [p["category"] if p else None for p in preds]
        pred_u = [bool(p and p["priority"] == "high") for p in preds]
        answered = [p is not None for p in preds]
        correct = [g == p for g, p in zip(gold_c, pred_c)]
        ans_correct = [c for c, a in zip(correct, answered) if a]
        per_class = {
            lab: round(sum(1 for g, p in zip(gold_c, pred_c) if g == lab and p == lab) / max(1, gold_c.count(lab)), 3)
            for lab in labels
        }
        return {
            "n": len(items),
            "coverage": round(sum(answered) / len(items), 3),
            "accuracy": round(sum(correct) / len(items), 3),
            "accuracy_when_answered": round(sum(ans_correct) / len(ans_correct), 3) if ans_correct else None,
            "macro_f1": macro_f1(gold_c, pred_c, labels),
            "urgency_f1": binary_f1(gold_u, pred_u),
            "recall_per_category": per_class,
            "latency_p50_s": pct(lat, 50) if lat else None,
            "latency_p95_s": pct(lat, 95) if lat else None,
        }

    results = {"engines": {}, "chains": {}, "labels": labels}
    for eng, out in raw.items():
        results["engines"][eng] = score([r for r, _ in out], [dt for _, dt in out])

    kw = [r for r, _ in raw.get("keyword", [])] or [ticket_service.keyword_triage(it["text"]) for it in items]
    for chain in (["llm"], ["laya"], ["laya", "llm"]):
        if not all(e in raw for e in chain):
            continue
        preds, lat = [], []
        for i in range(len(items)):
            res, total = None, 0.0
            for e in chain:
                r, dt = raw[e][i]
                total += dt
                if r:
                    res = r
                    break
            preds.append(res or kw[i])
            lat.append(total)
        results["chains"]["→".join(chain + ["keyword"])] = score(preds, lat)

    # Confusions of the best single engine, for the report's error analysis.
    best = max(results["engines"], key=lambda e: results["engines"][e]["accuracy"]) if results["engines"] else None
    if best:
        conf = Counter(
            (it["category"], (r or {}).get("category"))
            for it, (r, _) in zip(items, raw[best]) if not r or r["category"] != it["category"]
        )
        results["top_confusions"] = {"engine": best, "pairs": [[g, p, n] for (g, p), n in conf.most_common(8)]}
    return results


# ── 2. grounded Q&A ──────────────────────────────────────────────────────────
def eval_qa(api, users, pause):
    qs = json.loads((DATA / "qa_set.json").read_text(encoding="utf-8"))["questions"]
    rows = []
    for q in qs:
        email = users[q["role"]]
        body, dt = api.chat(email, q["question"])
        ans, srcs = body.get("response") or "", body.get("sources") or []
        refs = [(s.get("source_ref") or "").lower() for s in srcs]
        hit = any(any(exp.lower() in r for r in refs) for exp in q["expected_sources"])
        low = norm(ans)
        ok = True
        if q.get("must_include"):
            ok = any(norm(k) in low for k in q["must_include"])
        if q.get("must_include_all"):
            ok = ok and all(norm(k) in low for k in q["must_include_all"])
        rows.append({
            "id": q["id"], "role": q["role"], "retrieval_hit": hit, "correct": ok,
            "cited": bool(CITE_RE.search(ans)), "abstained": bool(ABSTAIN_RE.search(ans)),
            "latency_s": round(dt, 3), "answer": ans[:400], "sources": refs,
        })
        if pause:
            time.sleep(pause)

    def agg(sub):
        lat = [r["latency_s"] for r in sub]
        return {
            "n": len(sub),
            "retrieval_hit_at_5": round(sum(r["retrieval_hit"] for r in sub) / len(sub), 3),
            "answer_correct": round(sum(r["correct"] for r in sub) / len(sub), 3),
            "cited": round(sum(r["cited"] for r in sub) / len(sub), 3),
            "abstained": round(sum(r["abstained"] for r in sub) / len(sub), 3),
            "latency_p50_s": pct(lat, 50),
            "latency_p95_s": pct(lat, 95),
        }

    return {
        "overall": agg(rows),
        "student": agg([r for r in rows if r["role"] == "student"]),
        "staff": agg([r for r in rows if r["role"] == "staff"]),
        "items": rows,
    }


# ── 3. visibility ────────────────────────────────────────────────────────────
def eval_visibility(api, student, pause):
    spec = json.loads((DATA / "visibility_set.json").read_text(encoding="utf-8"))
    rows = []
    for q in spec["questions"]:
        body, dt = api.chat(student, q)
        ans, srcs = body.get("response") or "", body.get("sources") or []
        internal = [s.get("source_ref") for s in srcs if s.get("visibility") != "public"]
        forbidden = [f for f in spec["forbidden"] if norm(f) not in norm(q) and norm(f) in norm(ans)]
        rows.append({
            "question": q, "scope": body.get("scope"), "internal_sources": internal,
            "forbidden_in_answer": forbidden, "leak": bool(internal or forbidden), "latency_s": round(dt, 3),
        })
        if pause:
            time.sleep(pause)
    return {
        "n": len(rows),
        "leaks": sum(r["leak"] for r in rows),
        "internal_source_leaks": sum(bool(r["internal_sources"]) for r in rows),
        "forbidden_fact_leaks": sum(bool(r["forbidden_in_answer"]) for r in rows),
        "all_scoped_public": all(r["scope"] == "public" for r in rows),
        "items": rows,
    }


# ── 4. commitment extraction ─────────────────────────────────────────────────
def eval_commitments(api, staff):
    gold = json.loads((DATA / "commitments_gold.json").read_text(encoding="utf-8"))["meetings"]
    meetings = {m["id"]: m["title"] for m in api.get(staff, "/api/v1/transcripts")}
    extracted = api.get(staff, "/api/v1/commitments")

    def meeting_key(title):
        return next((k for k in gold if k.lower() in (title or "").lower()), None)

    by_meeting = defaultdict(list)
    for c in extracted:
        key = meeting_key(meetings.get(c.get("source_meeting_id")))
        if key:
            by_meeting[key].append(c)

    matched_gold, matched_ext, total_ext = 0, 0, 0
    details = {}
    for key, golds in gold.items():
        exts = by_meeting.get(key, [])
        total_ext += len(exts)
        used = set()
        hits = 0
        for g in golds:
            for i, c in enumerate(exts):
                if i in used:
                    continue
                desc, who = (c.get("description") or "").lower(), (c.get("assignee") or "").lower()
                if g["assignee"].lower() in who and any(k in desc for k in g["keywords"]):
                    used.add(i)
                    hits += 1
                    break
        matched_gold += hits
        matched_ext += len(used)
        details[key] = {"gold": len(golds), "extracted": len(exts), "matched": hits}
    total_gold = sum(len(v) for v in gold.values())
    prec = matched_ext / total_ext if total_ext else 0.0
    rec = matched_gold / total_gold if total_gold else 0.0
    return {
        "gold": total_gold, "extracted": total_ext, "matched": matched_gold,
        "precision": round(prec, 3), "recall": round(rec, 3),
        "f1": round(2 * prec * rec / (prec + rec), 3) if prec + rec else 0.0,
        "per_meeting": details,
    }


# ── report ───────────────────────────────────────────────────────────────────
def to_markdown(res):
    lines = [f"# Evaluation results — {res['run_at']}", "",
             f"Model: `{res['env'].get('llm_model')}` · laya: `{res['env'].get('laya')}` · dataset: synthetic (see `evaluation/data/`).",
             "Regenerate with `evaluation/run_eval.ps1`; numbers vary slightly between runs because LLM outputs vary.", ""]
    t = res.get("triage")
    if t:
        lines += ["## 1. Help-desk triage (96 labelled queries, 6 categories)", "",
                  "| Engine | Coverage | Accuracy | Macro-F1 | Urgency F1 | p50 latency (s) | p95 latency (s) |",
                  "|---|---|---|---|---|---|---|"]
        for name, s in list(t["engines"].items()) + list(t["chains"].items()):
            lines.append(f"| {name} | {s['coverage']:.0%} | {s['accuracy']:.1%} | {s['macro_f1']:.3f} | {s['urgency_f1']:.3f} | {s['latency_p50_s']} | {s['latency_p95_s']} |")
        lines += ["", "Engines alone count an abstention as wrong; chains fall back to the keyword classifier.", ""]
    q = res.get("qa")
    if q:
        lines += ["## 2. Grounded question answering (24 questions)", "",
                  "| Asked as | n | Retrieval hit@5 | Answer correct | Cited | Abstained | p50 (s) | p95 (s) |",
                  "|---|---|---|---|---|---|---|---|"]
        for k in ("student", "staff", "overall"):
            s = q[k]
            lines.append(f"| {k} | {s['n']} | {s['retrieval_hit_at_5']:.0%} | {s['answer_correct']:.0%} | {s['cited']:.0%} | {s['abstained']:.0%} | {s['latency_p50_s']} | {s['latency_p95_s']} |")
        lines.append("")
    v = res.get("visibility")
    if v:
        lines += ["## 3. Visibility (adversarial student queries)", "",
                  f"**{v['leaks']} leaks in {v['n']} queries** — {v['internal_source_leaks']} returned an internal source, "
                  f"{v['forbidden_fact_leaks']} stated an internal-only fact; every query scoped to public: {v['all_scoped_public']}.", ""]
    c = res.get("commitments")
    if c:
        lines += ["## 4. Commitment extraction (4 transcripts, hand-labelled)", "",
                  f"Gold {c['gold']} · extracted {c['extracted']} · matched {c['matched']} → "
                  f"**precision {c['precision']:.0%}, recall {c['recall']:.0%}, F1 {c['f1']:.2f}**.", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="triage,qa,visibility,commitments")
    ap.add_argument("--engines", default="keyword,llm,laya")
    ap.add_argument("--api", default=os.environ.get("EVAL_API", "http://backend:8001"))
    ap.add_argument("--out", default="/out")
    ap.add_argument("--pause", type=float, default=1.0, help="seconds between LLM calls (rate limits)")
    args = ap.parse_args()
    parts = {p.strip() for p in args.parts.split(",") if p.strip()}

    sys.path.insert(0, "/app")
    from app.core.config import settings

    try:
        import laya  # noqa: F401
        laya_version = laya.__version__
    except ImportError:
        laya_version = None

    res = {"run_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
           "env": {"llm_model": settings.LLM_MODEL, "laya": laya_version}}
    users = {"student": "aarav.desai@example.com", "staff": "karan.shah@example.com"}
    api = Api(args.api)

    if "triage" in parts:
        engines = [e for e in args.engines.split(",") if e and (e != "laya" or laya_version)]
        res["triage"] = eval_triage(engines, args.pause)
    if "qa" in parts:
        res["qa"] = eval_qa(api, users, args.pause)
    if "visibility" in parts:
        res["visibility"] = eval_visibility(api, users["student"], args.pause)
    if "commitments" in parts:
        res["commitments"] = eval_commitments(api, users["staff"])

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    (out / f"results-{stamp}.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "latest.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "RESULTS.md").write_text(to_markdown(res) + "\n", encoding="utf-8")
    print(to_markdown(res))


if __name__ == "__main__":
    main()
