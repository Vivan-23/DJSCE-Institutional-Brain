from sqlmodel import SQLModel, Field
from typing import Optional, List
from datetime import datetime, timezone
from uuid import UUID, uuid4

class UserBase(SQLModel):
    email: str = Field(unique=True, index=True)
    full_name: Optional[str] = None
    role: str = Field(default="employee")

class User(UserBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Document(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    title: str
    source_type: str
    storage_path: Optional[str] = None
    raw_content: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ProgressReport(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    reporter_id: UUID = Field(foreign_key="user.id")
    project_name: str
    report_date: datetime
    status: str
    accomplishments: Optional[str] = None
    roadblocks: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ActiveInsight(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    category: str
    observation: str
    impact_rationale: str
    suggested_actions: str  # JSON array stored as string
    confidence_score: float
    is_dismissed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ─────────────────────────────────────────────────────────────────────────────
# Company PA + Skill layer
#
# Complex/nested fields (lists, dicts) are stored as JSON-serialized strings to
# stay database-agnostic (the test suite runs on SQLite, prod on Postgres) —
# matching the existing `ActiveInsight.suggested_actions` convention.
# ─────────────────────────────────────────────────────────────────────────────

class Employee(SQLModel, table=True):
    """A person the Company PA serves. Optionally linked to a login User."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: Optional[UUID] = Field(default=None, foreign_key="user.id", index=True)
    display_name: str = Field(index=True)
    aliases: str = Field(default="[]")  # JSON list of name variants for matching
    manager_id: Optional[UUID] = Field(default=None, foreign_key="employee.id")
    timezone: str = Field(default="UTC")
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Meeting(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    title: str
    occurred_at: datetime
    summary: Optional[str] = None
    participants: str = Field(default="[]")  # JSON list of participant names
    source: str = Field(default="upload")  # upload / zoom / otter / fireflies / ...
    raw_transcript: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Fragment(SQLModel, table=True):
    """The shared evidence unit. Everything ingested becomes Fragments."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    source_type: str = Field(index=True)  # transcript/slack/email/ticket/doc/db/checkin/followup
    source_ref: Optional[str] = None  # permalink / external id
    author_employee_id: Optional[UUID] = Field(default=None, foreign_key="employee.id")
    meeting_id: Optional[UUID] = Field(default=None, foreign_key="meeting.id", index=True)
    content: str
    occurred_at: Optional[datetime] = None
    embedding_id: Optional[str] = None  # id of the vector in ChromaDB
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Commitment(SQLModel, table=True):
    """A first-class action item the PA tracks and follows up on."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    assignee_employee_id: Optional[UUID] = Field(default=None, foreign_key="employee.id", index=True)
    description: str
    source_meeting_id: Optional[UUID] = Field(default=None, foreign_key="meeting.id")
    source_fragment_id: Optional[UUID] = Field(default=None, foreign_key="fragment.id")
    due_date: Optional[datetime] = None
    status: str = Field(default="open")  # open / in_progress / blocked / done / dropped
    last_followup_at: Optional[datetime] = None
    confidence: float = Field(default=0.7)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CommitmentUpdate(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    commitment_id: UUID = Field(foreign_key="commitment.id", index=True)
    raw_text: str  # the employee's own words
    structured_summary: Optional[str] = None
    status_change: Optional[str] = None  # new status, if the update changed it
    source: str = Field(default="checkin")  # checkin / followup
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CheckIn(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    employee_id: UUID = Field(foreign_key="employee.id", index=True)
    date: datetime
    conversation: str = Field(default="[]")  # JSON list of {role, content} turns
    extracted_updates: str = Field(default="[]")  # JSON list of structured updates
    completed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Skill(SQLModel, table=True):
    """A structured, executable procedure — the agent-consumable deliverable."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True)
    description: str
    trigger: str
    preconditions: str = Field(default="[]")    # JSON list
    steps: str = Field(default="[]")            # JSON list
    decision_rules: str = Field(default="[]")  # JSON list
    guardrails: str = Field(default="[]")      # JSON list
    escalation: Optional[str] = None
    owner_employee_id: Optional[UUID] = Field(default=None, foreign_key="employee.id")
    status: str = Field(default="draft")  # draft / approved / stale / deprecated
    version: int = Field(default=1)
    last_verified_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SkillCitation(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    skill_id: UUID = Field(foreign_key="skill.id", index=True)
    fragment_id: UUID = Field(foreign_key="fragment.id")
    element: Optional[str] = None  # which step/rule this fragment supports


class AuditLog(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    actor: str  # employee email or agent id
    action: str  # extract / approve / skill_use / checkin / followup / ...
    target_id: Optional[str] = None
    audit_metadata: str = Field(default="{}")  # JSON object ("metadata" is reserved by SQLModel)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
