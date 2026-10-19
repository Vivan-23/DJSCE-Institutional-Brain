"""Figure 7.1: triage accuracy and macro-F1 per engine, read from results/RESULTS.md.

Run from the repository root:  python evaluation/publication_tools/fig7_1_triage.py
"""
import pathlib
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

base = pathlib.Path(__file__).resolve().parents[2] / "publication" / "01_ipd_report"
text = (base / "results" / "RESULTS.md").read_text(encoding="utf-8")
section = text.split("## 1.")[1].split("## 2.")[0]

rows = []
for line in section.splitlines():
    cells = [c.strip() for c in line.strip("|").split("|")]
    if len(cells) == 7 and cells[2].endswith("%"):
        rows.append((cells[0], float(cells[2].rstrip("%")), float(cells[3]) * 100))

labels = [r[0] for r in rows]
x = range(len(rows))
fig, ax = plt.subplots(figsize=(8, 3.6), dpi=200)
ax.bar([i - 0.2 for i in x], [r[1] for r in rows], width=0.4, label="Accuracy (%)", color="#5e6ad2")
ax.bar([i + 0.2 for i in x], [r[2] for r in rows], width=0.4, label="Macro-F1 (×100)", color="#9aa0a8")
for i, r in enumerate(rows):
    ax.text(i - 0.2, r[1] + 1.5, f"{r[1]:.1f}", ha="center", fontsize=7)
ax.set_xticks(list(x), labels, fontsize=8)
ax.set_ylim(0, 105)
ax.set_ylabel("Score")
run = re.search(r"# Evaluation results — (.+)", text)
ax.set_title(f"Help-desk triage, 96 queries ({run.group(1) if run else ''})", fontsize=10)
ax.spines[["top", "right"]].set_visible(False)
ax.legend(fontsize=8, frameon=False)
fig.tight_layout()
fig.savefig(base / "figures" / "fig7_1_triage.png")
print("wrote fig7_1_triage.png")
