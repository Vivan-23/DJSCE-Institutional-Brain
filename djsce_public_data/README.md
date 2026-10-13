# DJSCE Public Knowledge Dataset

Authentic, publicly published knowledge collected from the official college website [https://www.djsce.ac.in](https://www.djsce.ac.in) for the DJSCE Institutional Brain's Student Help Desk.

---

## 1. Overview & Crawl Metadata
- **Retrieved Date**: 2026-10-13
- **Root Target**: `https://www.djsce.ac.in/`
- **User-Agent**: `DJSCE-IPD-Student-Project (academic, non-commercial)`
- **Request Rate Limit**: Maximum 1 request/second globally
- **Total Pages / Resources Crawled**: 46 primary HTML pages + official Examination Manual & placement reports
- **Output Knowledge Files**: 26 topical `.txt` files in `kb/`
- **Audit Raw Cache**: `raw/` (git-ignored, contains cleaned raw text per page)

---

## 2. Crawl Rules & Ethical Constraints Observed
1. **Robots.txt & Sitemap Compliance**: `https://www.djsce.ac.in/robots.txt` was inspected prior to scraping (no disallowed paths detected).
2. **Polite Crawling**: Strict rate limit of 1 request per second was enforced across all crawls, with retry limit of 2 and automatic stop on 429/403.
3. **Public Pages Only**: Only publicly accessible institutional pages, circulars, and published manuals were crawled. No internal portals, ERP systems, SAP logins, or password-protected resources were accessed.
4. **Mandatory Privacy Protection**:
   - Zero personal email addresses, phone numbers, home addresses, dates of birth, or student records stored.
   - All contact details replaced with the standardized notice:
     `Official contact details are published on the DJSCE website.`
   - Verified via automated regex scanning (`@`, `\d{10}`, `022 \d`, `+91`, `DOB`, `Address:`).
5. **Traceability & Provenance**:
   - Every file begins with the mandatory first line header:
     `[PUBLIC DJSCE INFORMATION · Source: <url> · Retrieved: <YYYY-MM-DD> · Verify against the official DJSCE website for updates.]`
   - Every Q&A pair cites its direct official source URL.

---

## 3. Knowledge Base Breakdown by Section

| Section | Files | Topics Covered |
| :--- | :--- | :--- |
| **Institution & Governance** | 4 files | DJSCE overview, autonomous & empowered autonomous status, NAAC accreditation, SVKM Trust history, statutory bodies (Governing Body, Academic Council, BOS, IQAC), Core Values, Research Policy, and campus office location. |
| **Admissions & Policies** | 3 files | B.Tech branch intake (1140 total seats), CAP/ILS process, Direct Second Year (DSE), M.Tech & Ph.D. research centers, FRA fee structure, DTE cancellation rules, MahaDBT scholarships, and freeships. |
| **Academic Departments** | 9 files | Detailed profiles for all 9 departments: Computer Engineering, Information Technology, AI & Data Science, AI & Machine Learning, CSE (Data Science), CSE (IoT & Cyber Security with Blockchain), EXTC, Mechanical Engineering, and Basic Sciences & Humanities. |
| **Examinations & Evaluation** | 5 files | 75% attendance rule & condonation powers, 10-point grading matrix (O to F grades), SGPA/CGPA formula, Semester End Re-eval and Photocopy mechanism, examination hall discipline, scribe policy, and Honours/Minor degree criteria. |
| **Careers & Placements** | 2 files | Training & Placement cell roles, soft-skill training programs, AICTE internship guidelines, prominent recruiters (Google, Rubrik, Morgan Stanley, JPMC, ZS Associates), and published compensation figures (up to 160 LPA). |
| **Facilities & Student Life** | 3 files | AICTE IDEA Lab prototyping equipment (3D printers, CNC routers, laser cutters), student counselling facility, online grievance redressal cell, Divyangjan accessibility, and student chapters (ACM, CSI, IEEE, IETE, S4DS, Unicode, Antariksh, Trinity). |

**Total Files**: 26 files

---

## 4. Skipped Pages & Gaps
- **Files Larger than 10 MB**: Skipped heavy multimedia files and large student archives per ground rules.
- **Portals / Dashboards**: Ignored all links pointing to SAP portals, login gateways, or internal forms.
- **Image-only Scanned Circulars**: Certain archived circulars that consisted solely of scanned handwritten notices without OCR text were omitted to ensure 100% provenance and zero hallucination.

---

## 5. Team Notice & System Alignment
1. **Scope Alignment**: Update the project README, report, and mentor brief to reflect:
   > *"The DJSCE Institutional Brain combines synthetic committee meeting records with authentic, publicly published institutional knowledge from the official college website (https://www.djsce.ac.in), cited by URL and retrieval date."*
2. **Faculty / Guide Acknowledgement**: Ensure written acknowledgment from your project guide for utilizing the public website content for non-commercial academic research.
