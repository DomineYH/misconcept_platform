# Data Model: Misconception Dialogue Simulator

**Feature**: 001-misconception-dialogue-sim
**Date**: 2025-11-05
**Technology**: SQLAlchemy 2.x + SQLite3

## Entity Relationship Overview

```
User (teacher/admin)
  ↓ creates
Scenario ←→ AnalysisFramework
  ↓ used in
Session
  ↓ contains
Message
  ↓ analyzed by (if role=teacher)
QuestionAnalysis
  ↑ summarized in
SessionSummary
```

## Entity Definitions

### User

**Purpose**: Represents teachers, admins, or test students with
minimal authentication data

**Attributes**:
- `id`: Integer, primary key, auto-increment
- `student_uid`: Text, required, student unique identifier (login key)
- `nickname`: Text, required, display name (login key)
- `role`: Text, required, enum('teacher', 'student', 'admin'),
  default='teacher'
- `created_at`: DateTime, default=now()

**Constraints**:
- Unique constraint: (student_uid, nickname)
- Check constraint: role IN ('teacher', 'student', 'admin')

**Indexes**:
- Primary: id
- Unique: (student_uid, nickname)

**Validation Rules**:
- student_uid: 3-50 characters, alphanumeric + underscore
- nickname: 2-30 characters, any UTF-8
- role: Must be one of allowed enum values

**Relationships**:
- One-to-many: User → Session (teacher_id)
- One-to-many: User → Scenario (created_by)

**State Transitions**: None (simple CRUD entity)

**File Location**: `src/models/user.py` (~40 lines with validation)

---

### AnalysisFramework

**Purpose**: Defines classification system for pedagogical moves (e.g.,
high/low leverage question taxonomy)

**Attributes**:
- `id`: Integer, primary key, auto-increment
- `name`: Text, required, framework display name (e.g., "Leverage-Based
  Classification")
- `description`: Text, optional, framework explanation
- `labels_json`: Text, required, JSON array of label strings (e.g.,
  `["Pressing", "Linking", "Directing"]`)
- `created_at`: DateTime, default=now()

**Constraints**:
- Unique constraint: name
- Check constraint: labels_json must parse as valid JSON array

**Indexes**:
- Primary: id
- Unique: name

**Validation Rules**:
- name: 3-100 characters
- labels_json: Valid JSON array with 2-20 string elements
- Each label: 2-50 characters

**Relationships**:
- One-to-many: AnalysisFramework → Scenario (framework_id)

**State Transitions**: None

**File Location**: `src/models/analysis_framework.py` (~35 lines)

---

### Scenario

**Purpose**: Represents a dialogue situation with student misconception,
problem context, and active status

**Attributes**:
- `id`: Integer, primary key, auto-increment
- `title`: Text, required, scenario display name
- `prompt`: Text, required, internal system prompt defining misconception
  and problem
- `student_profile`: Text, optional, grade level and student
  characteristics
- `is_active`: Integer (boolean), required, default=1, controls
  visibility to teachers
- `framework_id`: Integer, foreign key → AnalysisFramework(id), required
- `created_by`: Integer, foreign key → User(id), optional
- `created_at`: DateTime, default=now()

**Constraints**:
- Foreign key: framework_id REFERENCES analysis_framework(id)
- Foreign key: created_by REFERENCES user(id)
- Check constraint: is_active IN (0, 1)

**Indexes**:
- Primary: id
- Index: is_active (for active scenario queries)
- Index: framework_id (for framework-filtered lists)

**Validation Rules**:
- title: 3-200 characters
- prompt: 10-10,000 characters (system prompt template)
- student_profile: 0-1,000 characters
- is_active: Must be 0 or 1

**Relationships**:
- Many-to-one: Scenario → AnalysisFramework (framework_id)
- Many-to-one: Scenario → User (created_by)
- One-to-many: Scenario → Session (scenario_id)

**State Transitions**:
- Active (is_active=1) ↔ Inactive (is_active=0) via admin toggle
- Cannot delete scenario with active sessions (foreign key constraint)

**File Location**: `src/models/scenario.py` (~50 lines with validation)

---

### Session

**Purpose**: Represents one teacher-student dialogue instance with start/
end timestamps

**Attributes**:
- `id`: Integer, primary key, auto-increment
- `scenario_id`: Integer, foreign key → Scenario(id), required
- `teacher_id`: Integer, foreign key → User(id), required
- `started_at`: DateTime, default=now()
- `ended_at`: DateTime, optional, null while active

**Constraints**:
- Foreign key: scenario_id REFERENCES scenario(id)
- Foreign key: teacher_id REFERENCES user(id)

**Indexes**:
- Primary: id
- Index: (teacher_id, started_at) for user session history
- Index: ended_at (for active session queries)

**Validation Rules**:
- ended_at: Must be >= started_at if not null
- Session duration: Typically 5-60 minutes (logged warning if > 2 hours)

**Relationships**:
- Many-to-one: Session → Scenario (scenario_id)
- Many-to-one: Session → User (teacher_id)
- One-to-many: Session → Message (session_id)
- One-to-one: Session → SessionSummary (session_id)

**State Transitions**:
- Active (ended_at=null) → Completed (ended_at=timestamp) when teacher
  ends session
- Auto-save triggered every 30s while active

**File Location**: `src/models/session.py` (~40 lines)

---

### Message

**Purpose**: Individual dialogue turn from teacher, student chatbot, or
tutor chatbot

**Attributes**:
- `id`: Integer, primary key, auto-increment
- `session_id`: Integer, foreign key → Session(id), required
- `role`: Text, required, enum('teacher', 'student', 'tutor')
- `content`: Text, required, message body
- `created_at`: DateTime, default=now()

**Constraints**:
- Foreign key: session_id REFERENCES session(id) ON DELETE CASCADE
- Check constraint: role IN ('teacher', 'student', 'tutor')

**Indexes**:
- Primary: id
- Index: (session_id, created_at) for chronological message retrieval
- Index: (session_id, role) for filtering teacher questions

**Validation Rules**:
- role: Must be one of allowed enum values
- content: 1-5,000 characters (prevent excessively long messages)
- created_at: Must be >= session.started_at

**Relationships**:
- Many-to-one: Message → Session (session_id, cascade delete)
- One-to-one: Message → QuestionAnalysis (message_id, if role=teacher)

**State Transitions**: None (immutable once created)

**File Location**: `src/models/message.py` (~35 lines)

---

### QuestionAnalysis

**Purpose**: Classification result for teacher messages using selected
analysis framework

**Attributes**:
- `id`: Integer, primary key, auto-increment
- `message_id`: Integer, foreign key → Message(id), required, unique
- `label`: Text, required, classification label (e.g., "Pressing",
  "Directing")
- `confidence`: Real, optional, classification confidence score (0.0-1.0)
- `meta_json`: Text, optional, JSON object with evidence and rationale

**Constraints**:
- Foreign key: message_id REFERENCES message(id) ON DELETE CASCADE
- Unique constraint: message_id (one analysis per message)
- Check constraint: confidence BETWEEN 0.0 AND 1.0 OR confidence IS NULL

**Indexes**:
- Primary: id
- Unique: message_id
- Index: label (for frequency aggregation)

**Validation Rules**:
- label: Must match one of framework labels for session's scenario
- confidence: 0.0-1.0 or null
- meta_json: Valid JSON object with keys: evidence, rationale

**Relationships**:
- One-to-one: QuestionAnalysis → Message (message_id, cascade delete)

**State Transitions**: None (immutable once analyzed)

**File Location**: `src/models/question_analysis.py` (~40 lines)

---

### SessionSummary

**Purpose**: Aggregated statistics and feedback for completed session

**Attributes**:
- `id`: Integer, primary key, auto-increment
- `session_id`: Integer, foreign key → Session(id), required, unique
- `distribution_json`: Text, required, JSON object mapping labels to
  counts (e.g., `{"Pressing": 5, "Linking": 2, "Directing": 8}`)
- `feedback`: Text, optional, LLM-generated summary and suggestions
- `created_at`: DateTime, default=now()

**Constraints**:
- Foreign key: session_id REFERENCES session(id) ON DELETE CASCADE
- Unique constraint: session_id (one summary per session)

**Indexes**:
- Primary: id
- Unique: session_id

**Validation Rules**:
- distribution_json: Valid JSON object with string keys and integer
  values >= 0
- feedback: 0-5,000 characters
- created_at: Must be >= session.ended_at

**Relationships**:
- One-to-one: SessionSummary → Session (session_id, cascade delete)

**State Transitions**: None (immutable once created)

**File Location**: `src/models/session_summary.py` (~35 lines)

## Schema Creation SQL

```sql
-- User table
CREATE TABLE user (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_uid TEXT NOT NULL,
  nickname TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('teacher','student','admin'))
    DEFAULT 'teacher',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(student_uid, nickname)
);

-- Analysis Framework table
CREATE TABLE analysis_framework (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  labels_json TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Scenario table
CREATE TABLE scenario (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  prompt TEXT NOT NULL,
  student_profile TEXT,
  is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
  framework_id INTEGER NOT NULL REFERENCES analysis_framework(id),
  created_by INTEGER REFERENCES user(id),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_scenario_active ON scenario(is_active);
CREATE INDEX idx_scenario_framework ON scenario(framework_id);

-- Session table
CREATE TABLE session (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scenario_id INTEGER NOT NULL REFERENCES scenario(id),
  teacher_id INTEGER NOT NULL REFERENCES user(id),
  started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  ended_at DATETIME
);
CREATE INDEX idx_session_teacher_started ON session(teacher_id,
  started_at);
CREATE INDEX idx_session_ended ON session(ended_at);

-- Message table
CREATE TABLE message (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES session(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK(role IN ('student','teacher','tutor')),
  content TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_message_session_created ON message(session_id,
  created_at);
CREATE INDEX idx_message_session_role ON message(session_id, role);

-- Question Analysis table
CREATE TABLE question_analysis (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  message_id INTEGER NOT NULL UNIQUE REFERENCES message(id)
    ON DELETE CASCADE,
  label TEXT NOT NULL,
  confidence REAL CHECK(confidence BETWEEN 0.0 AND 1.0
    OR confidence IS NULL),
  meta_json TEXT
);
CREATE INDEX idx_question_analysis_label ON question_analysis(label);

-- Session Summary table
CREATE TABLE session_summary (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL UNIQUE REFERENCES session(id)
    ON DELETE CASCADE,
  distribution_json TEXT NOT NULL,
  feedback TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## Data Access Patterns

### High-Frequency Queries

1. **Active Scenario List** (teacher home page):
   ```sql
   SELECT id, title, student_profile FROM scenario
   WHERE is_active = 1 ORDER BY created_at DESC;
   ```

2. **Session Message History** (dialogue UI):
   ```sql
   SELECT role, content, created_at FROM message
   WHERE session_id = ? ORDER BY created_at ASC;
   ```

3. **Teacher Question Classifications** (analysis display):
   ```sql
   SELECT m.content, qa.label, qa.confidence
   FROM message m JOIN question_analysis qa ON m.id = qa.message_id
   WHERE m.session_id = ? AND m.role = 'teacher'
   ORDER BY m.created_at ASC;
   ```

### Write Patterns

- **Frequent**: Message inserts (every 5-30 seconds during dialogue)
- **Moderate**: Session updates (start/end), question analysis inserts
- **Rare**: Scenario CRUD, framework management, user registration

### Optimization Notes

- SQLite WAL mode enables concurrent reads during message inserts
- Message table will grow quickly; consider archiving sessions > 6
  months old
- QuestionAnalysis meta_json allows schema evolution without migrations
- Use `EXPLAIN QUERY PLAN` to verify index usage on high-frequency
  queries

## Migration Strategy

**Initial Schema**: Create all tables with CREATE TABLE statements
above

**Future Changes**:
- Use Alembic if schema changes become frequent (>3 migrations in 3
  months)
- For MVP, manual schema updates acceptable (SQLite ALTER TABLE
  limited)
- Test migrations on copy of production database before applying

## Data Seeding (Development/Testing)

**Required Seed Data**:
1. Default AnalysisFramework: "High/Low Leverage" with labels
   `["Pressing", "Linking", "Directing", "Recall"]`
2. Admin user: student_uid="admin", nickname="Administrator",
   role="admin"
3. Sample scenario: Title="Fraction Addition Misconception",
   framework_id=1

**Seed Script Location**: `src/db/seed.py` (creates seed data if tables
empty)
