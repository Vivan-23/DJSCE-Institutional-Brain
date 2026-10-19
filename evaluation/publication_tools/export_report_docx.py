"""Export the IPD report draft to Word, with all figures and the reference list appended.

Needs pandoc (`pip install pypandoc-binary`). Run from the repository root:
    python evaluation/publication_tools/export_report_docx.py
Writes publication/01_ipd_report/IPD_Report_final_draft.docx.
"""
import os
import pathlib
import re

import pypandoc

report = pathlib.Path(__file__).resolve().parents[2] / "publication" / "01_ipd_report"
src = (report / "REPORT_DRAFT.md").read_text(encoding="utf-8")
rows = re.findall(r"^\| (\d+\.\d+) \| ([^|]+) \| `([^`]+)` \|$", src, re.M)
figs = "\n\n# Appendix: Figures\n\n" + "\n\n".join(
    f"![Figure {n}: {t.strip()}](figures/{f}){{width=6in}}" for n, t, f in rows
)
refs = (report / "references.md").read_text(encoding="utf-8")
refs = refs.split("## Still to add")[0].replace("# References (IEEE style)", "# Appendix: References")
body = src.replace(
    "See `references.md` (IEEE style, numbered in order of first citation; every entry verified).", ""
)
os.chdir(report)
pypandoc.convert_text(body + figs + "\n\n" + refs, "docx", format="markdown",
                      outputfile="IPD_Report_final_draft.docx", extra_args=["--resource-path=."])
print(f"wrote IPD_Report_final_draft.docx with {len(rows)} figures")
