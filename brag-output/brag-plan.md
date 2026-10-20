# /brag plan — DJSCE Institutional Brain

Two cuts: **`brag.mp4`** — the full feature tour (2:18, every feature explained; source
`work/composition-full.html`, music `python work/music.py work/timeline.json work/music-full.wav`) — and
**`brag-short.mp4`** — the original 40 s cut (source `work/composition-short.html`, music `python work/music.py`).

## Full tour storyboard (2:18, 1920×1080, 30 fps)

| # | Group | Scene | Signed in as | Shows |
|---|---|---|---|---|
| — | — | Hook (4 s) · Name (4.5 s) · "One platform. Four roles." (6 s) | — | — |
| 1 | Meetings & tasks | Paste the minutes | Coordinator | Record form with IQAC sample, transcript → Extract button (not submitted) |
| 2 | Meetings & tasks | Every meeting, summarised | Coordinator | Summary, attendees, decisions, Download DOCX/PDF |
| 3 | Meetings & tasks | Commitments with an owner | Coordinator | My Work card: progress, due date, assigned by |
| 4 | Meetings & tasks | Just say what you did today | Faculty | Follow-up question + typed check-in (not sent) |
| 5 | Meetings & tasks | Nothing slips through | Coordinator | Overview stats + deadline insights |
| 6 | Knowledge | How things are done here | Coordinator | Status filters (draft/approved/needs review/retired) + procedure steps |
| 7 | Knowledge | Upload once. Choose who sees it | Coordinator | File chosen, Public selected (not uploaded) |
| 8 | Knowledge | Ask anything. Get the source | Coordinator | Question → cited answer |
| 9 | Knowledge | See exactly where it came from | Coordinator | Expanded source list, internal/public tags |
| 10 | Students | Students get instant answers | Student | Help Desk answer, public information only |
| 11 | Students | Internal stays internal | Student | Same Academic Council question → no internal records |
| 12 | Students | Not answered? Raise a ticket | Student | Ticket form filled (not submitted), My tickets |
| 13 | Students | AI drafts. A person sends | Coordinator | Triage + unsent draft |
| 14 | Campus | Notices to exactly the right students | Coordinator → Student | Audience filters ("reaches 6 people", not sent) → student inbox |
| 15 | Campus | Deadlines that remind you | Coordinator | Reminders + calendar items |
| 16 | Insight & admin | See how it all connects | Coordinator | Knowledge graph |
| 17 | Insight & admin | Know what is working | Coordinator | Analytics |
| 18 | Insight & admin | Ready for a whole college | Admin | Users table |
| — | — | Results (7 s) · Outro (4.5 s) | — | 90.6 % · 91 % · 0 leaks |

Length: 2:18 rather than 2:00 so every caption stays on screen long enough to read (~0.3 s per word).
No demo data was changed while capturing: forms were filled on screen but never submitted.

---

## Short cut (40 s) — original plan

**What it is:** A college platform that turns committee meetings and documents into tracked commitments,
reviewed procedures and cited answers, with a student help desk that only answers from public information.
**For:** committee coordinators, faculty and students at an engineering college.
**What sets it apart:** every answer shows its sources; a person approves procedures and sends replies;
students can't see internal records (0 leaks in 20 attack questions).
**Most impressive claim:** 91 % of answers correct, every right source found, 0 leaks (measured 19 Oct 2026).
**Visual hook:** a meeting promise floating away untracked, then caught.
**Tone:** `polished` with app-store feature cards: serious, clean, project's own Linear-style look.
**Share caption:** see `share-copy.txt`.

**Length:** about 40 s instead of brag's usual 20 s: the user asked for a video that explains the features,
so each feature gets its own readable scene.

**Visual identity (from `frontend/src/app/globals.css`):** background `#08090a`, panel `#0f1011`, accent
indigo `#5e6ad2` → `#7170ff`, text `#f7f8f8` / `#8a8f98`, Inter. App screens are real captures of the running
app (19 Oct 2026), shown inside the app's own inset window and animated (zoom to the part that matters,
highlight box, cursor).

**Data note:** all people, meetings and tasks on screen are the project's synthetic demo data (fictional names,
example.com accounts); no real personal data. The "Demonstration prototype" banner stays visible.

## Storyboard (40 s, 1920×1080, 30 fps)

| # | Time | Scene | On screen |
|---|---|---|---|
| 1 | 0.0–4.0 | Hook | "Every committee meeting makes promises." → "Who keeps track of them?" |
| 2 | 4.0–8.0 | Reveal | Logo tile + "DJSCE Institutional Brain" + "Meetings, procedures and student questions — answered with sources." |
| 3 | 8.0–14.0 | Meetings → commitments | Meetings list → My Work card zoom. Caption "Minutes in. Commitments out — with an owner and a due date." |
| 4 | 14.0–19.5 | Procedures | Procedure detail, zoom on steps. Caption "Procedures a coordinator approves before anyone relies on them." |
| 5 | 19.5–25.0 | Cited assistant | Question typed, answer with [3] and "5 sources". Caption "Every answer cites its source." |
| 6 | 25.0–31.0 | Student help desk | Student answer, "public information only" highlighted → ticket draft "AI-suggested reply (not sent)". Caption "Students get answers from public information. AI drafts — a person sends." |
| 7 | 31.0–36.5 | Results | Three stat cards: 90.6 % tickets routed right · 91 % answers correct · 0 leaks to students |
| 8 | 36.5–40.0 | Outro | Name, "Department of Computer Engineering · DJSCE", "Demonstration prototype · synthetic committee data" |

**Sound:** one generated track: warm pad in A minor-ish progression (Am–F–C–G) at 100 bpm, soft kick and
hat from scene 3, a gentle rise into the results, soft chime (in key) on each stat card; effects mixed
under the music; fade out at the end.
