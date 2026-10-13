"""
Transcript service.

Normalizes a meeting transcript into a Meeting row + per-utterance Fragments,
runs meeting extraction (summary, decisions, commitments), and persists the
results. This is the Phase-1 capture entry point; the document-upload pipeline
remains for generic docs.

Transcript format is permissive. Lines like:
    Alex Chen: We should ship the refund flow this week.
    [00:03] Priya: I'll own the API changes.
are split into speaker-attributed fragments. Plain prose also works (one block).
"""
import json
import re
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import structlog
from sqlmodel import Session

from app.models.structured import Meeting
from app.services.employee_service import employee_service
from app.services.extraction_service import extraction_service
from app.services.fragment_service import fragment_service
from app.services.commitment_service import commitment_service

log = structlog.get_logger()

# "Alex Chen:" or "[00:12] Alex Chen:" at the start of a line
_SPEAKER_RE = re.compile(r"^\s*(?:\[[^\]]*\]\s*)?([A-Z][\w.\- ]{1,40}?):\s*(.+)$")


class TranscriptService:
    def ingest(
        self,
        db: Session,
        *,
        transcript: str,
        title: str,
        occurred_at: Optional[datetime] = None,
        source: str = "upload",
    ) -> dict:
        """
        Full pipeline: create Meeting -> extract -> store summary + Fragments +
        Commitments. Returns a summary dict for the API/task caller.
        """
        occurred_at = occurred_at or datetime.now(timezone.utc)

        # 1. Extract structured knowledge from the raw transcript
        extracted = extraction_service.extract_meeting(transcript)

        # 2. Persist the meeting
        meeting = Meeting(
            title=title,
            occurred_at=occurred_at,
            summary=extracted.get("summary") or None,
            participants=json.dumps(extracted.get("participants") or []),
            source=source,
            raw_transcript=transcript[:50_000],
        )
        db.add(meeting)
        db.commit()
        db.refresh(meeting)

        # 3. Split into speaker-attributed fragments and index them
        fragment_count = self._store_fragments(db, transcript, meeting.id, occurred_at, title)

        # 4. Create commitments from the extraction
        commitments = commitment_service.create_from_meeting(
            db, meeting, extracted.get("commitments") or []
        )

        log.info(
            "Transcript ingested",
            meeting_id=str(meeting.id),
            fragments=fragment_count,
            decisions=len(extracted.get("decisions") or []),
            commitments=len(commitments),
        )
        return {
            "meeting_id": str(meeting.id),
            "title": title,
            "summary": meeting.summary,
            "fragments": fragment_count,
            "decisions": extracted.get("decisions") or [],
            "commitments_created": len(commitments),
        }

    def _store_fragments(
        self, db: Session, transcript: str, meeting_id: UUID, occurred_at: datetime, title: str
    ) -> int:
        count = 0
        for speaker, utterance in self._split_utterances(transcript):
            author = employee_service.resolve_or_create(db, speaker) if speaker else None
            fragment_service.create_fragment(
                db,
                source_type="transcript",
                source_ref=title,  # provenance: which meeting this utterance came from
                content=utterance,
                author_employee_id=author.id if author else None,
                meeting_id=meeting_id,
                occurred_at=occurred_at,
            )
            count += 1
        return count

    @staticmethod
    def _split_utterances(transcript: str) -> list[tuple[Optional[str], str]]:
        """Yield (speaker, text) pairs. Falls back to paragraph blocks if unstructured."""
        utterances: list[tuple[Optional[str], str]] = []
        matched_any = False
        for line in transcript.splitlines():
            if not line.strip():
                continue
            m = _SPEAKER_RE.match(line)
            if m:
                matched_any = True
                utterances.append((m.group(1).strip(), m.group(2).strip()))
            elif utterances and matched_any:
                # Continuation of the previous speaker's turn
                prev_speaker, prev_text = utterances[-1]
                utterances[-1] = (prev_speaker, f"{prev_text} {line.strip()}")

        if matched_any:
            return utterances

        # Unstructured transcript: chunk into paragraph blocks with no speaker
        blocks = [b.strip() for b in re.split(r"\n\s*\n", transcript) if b.strip()]
        return [(None, b) for b in blocks] or [(None, transcript.strip())]


transcript_service = TranscriptService()
