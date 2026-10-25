# Setting up a department

> A runbook for bringing one department onto the Institutional Brain with real people and timetables.
> The first run (Computer Engineering, Oct–Nov 2026) is done **by hand** on purpose: each step records what it
> needed and what went wrong, so later departments can follow a checklist and the slow steps can be automated.
> Last verified: 2026-10-25 (written before the first run; update it as you go).

**Who does what**
- **System Administrator**: one named admin account (see step 0). Creates accounts and roles, and owns this runbook.
- **Committee Coordinator(s)** of the department: upload timetables, confirm faculty initials, publish, assign work.
- **Faculty**: log in, check My Schedule, and report anything wrong.

**Real data stays out of git.** Names, emails, initials and timetable files go into the running app (through the UI)
and into the local `onboarding/` folder, which git ignores. Never add them to `institution.yaml`, `mock_institutional_data/`
or anything else that is committed. The demo people in `institution.yaml` stay synthetic.

---

## 0. Administrator account (once per installation)

| | |
|---|---|
| Where | Log in as the demo admin → **Users** → Add user |
| Needs | Name and email of the person who will administer the system |
| Steps | 1. Create the account with role **System Administrator**; note the temporary password and change it. 2. Log in as the new admin. 3. On **Users**, deactivate `admin@example.com` (the demo admin). |
| Done when | Only the named admin is an active System Administrator. The app refuses to deactivate the last active admin, so step 3 only works after step 1. |
| Notes | `institution.yaml` only *creates* missing people, so a restart does not bring the demo admin back. Keep other demo accounts only on demo installs. |

## 1. Department entry

| | |
|---|---|
| Where | `institution.yaml` → `departments:` (committed; codes and names are public information) |
| Needs | Department code (e.g. `CE`) and full name |
| Done when | The code appears in the department dropdowns on **Users** and in uploads. Requires a backend restart. |

## 2. Collect the faculty roster

| | |
|---|---|
| Where | A local spreadsheet in `onboarding/<DEPT>/faculty.csv` (git-ignored) |
| Needs, per person | Full name as printed on timetables, **initials as used on timetables** (KD, LD…), official email, role (Faculty / Committee Coordinator), department |
| Sources | Department office list; the legend at the bottom of each class timetable (subject → faculty name) |
| Watch for | Two people with the same initials; the same person printed with different initials on different sheets; visiting faculty; spelling differences between sheets |
| Done when | Every set of initials that appears on any of the department's timetables is on the roster with exactly one person |

## 3. Create accounts

| | |
|---|---|
| Where | **Users** → Add user (by hand for this run). Bulk alternative: on **Users**, "Or import a CSV" under Add user, with columns `email,full_name,role,department` |
| Roles | Faculty = **Faculty** (`employee`); coordinators = **Committee Coordinator** (`manager`) |
| Passwords | A temporary password is shown once per account; hand it to the person privately |
| Done when | Every roster row has an active account in the right department and role |

## 4. Map faculty initials

| | |
|---|---|
| Where | **Timetables → Faculty initials** (or while reviewing an upload) |
| Needs | The roster's initials column |
| Done when | Every set of initials on the roster is mapped to its account. Mapping is global across all timetables |

## 5. Upload and review timetables

| | |
|---|---|
| Where | **Timetables → Uploads**, then open each draft |
| Needs | One file per class/division: the best available source (Word/Excel > PDF > photo; a straight, glare-free photo if that is all there is) |
| Per file, check | Class, division, semester, term, "applies from" date · every entry against the sheet (photos especially: cells read one row off, letters misread, cells missed) · labs with batches · parallel electives · nothing flagged *Fix* |
| Done when | Each class has one published timetable and its faculty have been notified |

## 6. Holidays and academic dates

| | |
|---|---|
| Where | Holidays that cancel teaching: **Timetables → Date changes**. Calendar dates (exams, terms): `institution.yaml` → `academic_calendar` |
| Done when | The term's known holidays are entered. Synthetic demo dates are removed or clearly labelled |

## 7. Check with faculty

| | |
|---|---|
| Where | Each faculty member: **My Work → My Schedule** (week view) and **Calendar → My Timetable** |
| Done when | Each faculty member (or a sample, for a large department) confirms their week is right. Fix errors on the class timetable, not per person |

---

## Run log

Fill in during each department's run. These rows are the evidence for what to automate next.

| Date | Dept | Step | Time taken | What was needed / what went wrong | Automation idea |
|---|---|---|---|---|---|
| | CE | 0 | | | |
| | CE | 2 | | | |
| | CE | 3 | | | |
| | CE | 4 | | | |
| | CE | 5 | | | |

## Automation candidates (to confirm from the run log)

- An `initials` column on the CSV import that creates the account and the confirmed mapping together (steps 3 + 4).
- Building the roster from the timetable legends: names from the legend, initials from the cells (step 2), still confirmed by a person.
- Uploading a whole department's timetables at once (already supported), plus one screen showing which classes are still unpublished.
- A per-department "setup status" page tracking steps 0–7.
