from sqlmodel import SQLModel, Field
from typing import Optional, List
from datetime import datetime, timezone
from uuid import UUID, uuid4

class UserBase(SQLModel):
    email: str = Field(unique=True, index=True)
    full_name: Optional[str] = None
    role: str = Field(default="student")  # student | employee | manager | admin
    department: Optional[str] = None  # department code (institution.yaml); scopes what they retrieve
    # Student cohort (used to address notices): year of study 1-4 (FE/SE/TE/BE), semester 1-8, division.
    year: Optional[int] = None
    semester: Optional[int] = None
    division: Optional[str] = None
    is_active: bool = Field(default=True)  # deactivated users cannot sign in; history is kept

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
# Faculty Desk PA + procedure ("skill") layer
#
# Complex/nested fields (lists, dicts) are stored as JSON-serialized strings to
# stay database-agnostic (the test suite runs on SQLite, prod on Postgres) —
# matching the existing `ActiveInsight.suggested_actions` convention.
# ─────────────────────────────────────────────────────────────────────────────

class Employee(SQLModel, table=True):
    """A staff member the Faculty Desk PA serves. Optionally linked to a login User."""
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
    decisions: str = Field(default="[]")  # JSON list of decisions extracted from the transcript
    source: str = Field(default="upload")  # upload / zoom / otter / fireflies / ...
    raw_transcript: Optional[str] = None
    department: str = Field(default="all", index=True)  # owning department code, or "all"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Fragment(SQLModel, table=True):
    """The shared evidence unit. Everything ingested becomes Fragments."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    source_type: str = Field(index=True)  # transcript/document/checkin/followup/ticket/<connector>
    source_ref: Optional[str] = None  # permalink / external id / filename
    source_url: Optional[str] = None  # public web page the content was taken from (cited to students)
    # Set for the searchable copy of an approved procedure (source_type="procedure").
    skill_id: Optional[UUID] = Field(default=None, foreign_key="skill.id", index=True)
    # Who may retrieve this evidence: "internal" (staff only) or "public" (students too).
    visibility: str = Field(default="internal", index=True)
    # Owning department code, or "all" (institution-wide). Scopes retrieval for students/faculty.
    department: str = Field(default="all", index=True)
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
    # open / in_progress / blocked / review (owner says done, awaiting confirmation) / done (confirmed) / dropped
    status: str = Field(default="open")
    last_followup_at: Optional[datetime] = None
    confidence: float = Field(default=0.7)
    # Progress tracking (owner updates, or the Faculty Desk check-in estimates it).
    progress: int = Field(default=0)  # 0-100
    remaining: Optional[str] = None  # what is left, in a line
    blocked_reason: Optional[str] = None
    # Who assigned it: the coordinator who created it, or who uploaded the source meeting.
    assigned_by: Optional[str] = None
    assigned_by_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    department: str = Field(default="all", index=True)  # scope; from the meeting or set on creation
    marked_done_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    confirmed_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CommitmentUpdate(SQLModel, table=True):
    """One entry in a commitment's timeline: a check-in, follow-up reply, note or status change."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    commitment_id: UUID = Field(foreign_key="commitment.id", index=True)
    raw_text: str  # the person's own words (or a description of the action)
    structured_summary: Optional[str] = None
    status_change: Optional[str] = None  # new status, if the update changed it
    progress: Optional[int] = None  # new progress, if the update changed it
    actor: Optional[str] = None  # who made the update
    source: str = Field(default="checkin")  # checkin / followup / owner / coordinator / note
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
    status: str = Field(default="draft")  # draft (in review) / approved / stale / deprecated (retired) / rejected
    version: int = Field(default=1)
    last_verified_at: Optional[datetime] = None
    # Ownership and review: the office that maintains it, and when it must be re-checked.
    owner_office: Optional[str] = None
    review_by: Optional[datetime] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    # Who may see it: internal (staff) or public (students see student_summary only); department or "all".
    visibility: str = Field(default="internal")
    department: str = Field(default="all", index=True)
    category: Optional[str] = None  # help-desk category key, e.g. "examinations"
    student_summary: Optional[str] = None  # plain "what you need to do" text for students
    origin: str = Field(default="extracted")  # extracted / manual
    reject_reason: Optional[str] = None
    stale_reason: Optional[str] = None
    stale_evidence: str = Field(default="[]")  # JSON list of the excerpts that contradicted it
    use_count: int = Field(default=0)  # answers / drafts that cited it
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SkillVersion(SQLModel, table=True):
    """A frozen copy of a procedure each time a version is approved (history + "what changed")."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    skill_id: UUID = Field(foreign_key="skill.id", index=True)
    version: int
    snapshot: str  # JSON of the procedure fields at approval
    approved_by: Optional[str] = None
    approved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


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


# ─────────────────────────────────────────────────────────────────────────────
# Student Help Desk
# ─────────────────────────────────────────────────────────────────────────────

class Ticket(SQLModel, table=True):
    """A help-desk query raised by a student (or staff). AI triages and drafts;
    a staff member reviews and sends the reply — the AI never answers directly."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    raised_by_user_id: UUID = Field(foreign_key="user.id", index=True)
    subject: str
    description: str
    status: str = Field(default="open", index=True)  # open / answered / closed
    # Triage (AI or keyword fallback) — category keys come from institution.yaml.
    category: str = Field(default="general", index=True)
    priority: str = Field(default="normal")  # low / normal / high
    routed_to: str = Field(default="Help Desk")
    triage_method: str = Field(default="keyword")  # keyword / llm
    triage_rationale: Optional[str] = None
    # Staff-only AI draft + the evidence it was grounded in (JSON list).
    ai_draft_reply: Optional[str] = None
    ai_sources: str = Field(default="[]")
    # The human-approved reply the requester sees.
    reply: Optional[str] = None
    replied_by_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    replied_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class QueryLog(SQLModel, table=True):
    """One assistant question, kept for analytics (most-asked questions, knowledge gaps).
    Deliberately has no user id: only the asker's role and department."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    question: str
    role: str = Field(index=True)
    department: Optional[str] = None
    source_count: int = 0  # 0 = nothing relevant was retrieved (a knowledge gap)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)


class Notice(SQLModel, table=True):
    """A message from staff to an audience of users chosen by filters."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    sender_user_id: UUID = Field(foreign_key="user.id", index=True)
    title: str
    body: str
    priority: str = Field(default="normal")  # normal / urgent
    # Filters as sent (JSON): {"roles": [...], "departments": [...], "years": [...], "semesters": [...], "divisions": [...]}
    audience: str = Field(default="{}")
    expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)


class NoticeRecipient(SQLModel, table=True):
    """Who a notice was addressed to, fixed at send time; read_at tracks reading."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    notice_id: UUID = Field(foreign_key="notice.id", index=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    read_at: Optional[datetime] = None

