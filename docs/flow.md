# Misconcept Platform - System Architecture & Flow

> **Last Updated**: 2026-02-15
> **Version**: 1.0

---

## 1. System Overview

**"Misconception Correction Dialogue Simulator"** - AI-powered platform where teachers practice questioning skills by conversing with an AI student bot that deliberately holds misconceptions.

```
+---------------------------------------------------------------+
|                      Browser (HTMX + JS)                      |
+---------------------------------------------------------------+
         |                    |                    |
    [Login/Auth]        [Teacher Chat]       [Admin Panel]
         |                    |                    |
+---------------------------------------------------------------+
|                    FastAPI Application                         |
|  +----------+  +----------+  +----------+  +----------+      |
|  |   Auth   |  | Sessions |  | Scenarios|  |  Admin   |      |
|  |  Routes  |  |  Routes  |  |  Routes  |  |  Routes  |      |
|  +----------+  +----------+  +----------+  +----------+      |
|       |              |              |              |           |
|  +----+--------------+--------------+-----------+  |          |
|  |              Service Layer                    |  |          |
|  |  SessionManager | StudentBot | TutorBot      |  |          |
|  |  Analyzer | MisconceptionAnalyzer | Export   |  |          |
|  +----------------------------------------------+  |          |
|       |                                             |          |
|  +----+---------------------------------------------+         |
|  |          SQLAlchemy ORM (Async)                   |         |
|  +---------------------------------------------------+        |
+---------------------------------------------------------------+
         |                                      |
   +----------+                          +----------+
   |  SQLite  |                          | OpenAI   |
   |   (WAL)  |                          | API      |
   +----------+                          +----------+
```

---

## 2. Middleware Stack

Requests pass through middleware in the following order:

```mermaid
flowchart TD
    REQ[Incoming Request] --> LM[LoggingMiddleware<br/>Request timing & logging]
    LM --> SH[SecurityHeadersMiddleware<br/>CSP, HSTS, X-Frame-Options]
    SH --> CORS[CORSMiddleware<br/>Cross-origin access control]
    CORS --> CSRF[CSRFMiddleware<br/>Double Submit Cookie<br/>Header: x-csrf-token]
    CSRF --> SM[SessionMiddleware<br/>Cookie-based auth<br/>8hr max-age, HttpOnly]
    SM --> RL[Rate Limiter<br/>slowapi: 5-30 req/min]
    RL --> APP[Route Handler]
    APP --> RES[Response]
```

**CSRF Exempt URLs**: `/health`, `/metrics`, `/login`, `/logout`

---

## 3. Authentication Flow

```mermaid
sequenceDiagram
    actor T as Teacher/Admin
    participant B as Browser
    participant S as FastAPI Server
    participant DB as SQLite

    T->>B: Visit /login
    B->>S: GET /login
    S-->>B: login.html

    T->>B: Submit credentials
    B->>S: POST /login (username, password)
    S->>DB: SELECT user WHERE username = ?
    DB-->>S: User record
    S->>S: bcrypt.checkpw(password, hash)

    alt Valid Credentials
        S->>S: Create session cookie<br/>{user_id, username, nickname, role, group_id}
        S-->>B: 302 Redirect -> /scenarios
    else Invalid
        S-->>B: login.html + error message
    end

    Note over B,S: All subsequent requests carry session cookie

    T->>B: Click logout
    B->>S: POST /logout
    S->>S: Clear session
    S-->>B: 302 Redirect -> /login
```

---

## 4. Main Dialogue Flow (Core Feature)

```mermaid
sequenceDiagram
    actor T as Teacher
    participant B as Browser
    participant API as FastAPI
    participant SM as SessionManager
    participant SB as StudentBot
    participant MA as MisconceptionAnalyzer
    participant TB as TutorBot
    participant DB as SQLite
    participant AI as OpenAI API

    T->>B: Visit /scenarios
    B->>API: GET /scenarios
    API->>DB: Load scenarios (filtered by user group)
    DB-->>API: Scenario list
    API-->>B: scenarios.html

    T->>B: Select scenario
    B->>API: GET /scenarios/{id}
    API->>DB: Validate group access
    API->>DB: INSERT new Session
    API-->>B: chat.html (session_id)

    loop Each Teacher Message
        T->>B: Type question
        B->>API: POST /sessions/{id}/messages
        API->>SM: process_teacher_message()

        SM->>DB: Save teacher Message

        Note over SM,SB: Step 1: Student response (sequential)
        SM->>SB: generate_response()
        SB->>AI: Responses API (system prompt + history)
        AI-->>SB: Student reply + usage

        Note over SM,TB: Step 2: Analysis + Tutor (parallel)
        par Misconception Analysis
            SM->>MA: analyze_student_response()
            MA->>AI: Responses API
            AI-->>MA: misconception_strength, evidence
        and Tutor Feedback (if enabled)
            SM->>TB: generate_feedback()
            TB->>AI: Responses API
            AI-->>TB: Pedagogical feedback (or None)
        end

        SM->>DB: Save student Message (with analysis_metadata)

        alt Tutor returned feedback
            SM->>DB: Save tutor Message
        end

        SM->>DB: Log API usage
        SM-->>API: Response messages
        API-->>B: HTMX message partials
    end

    T->>B: End session
    B->>API: POST /sessions/{id}/end
    API->>DB: Set ended_at
    API-->>B: JSON {ended: true, ended_at}

    T->>B: Click analyze
    B->>API: POST /sessions/{id}/analyze
    API-->>B: JSON {distribution, feedback}
```

---

## 5. Analysis Pipeline

```mermaid
flowchart TD
    START[POST /sessions/{id}/analyze] --> LOAD[Load all Messages from session]
    LOAD --> FILTER[Filter Greetings - Analyzer.detect_greetings]
    FILTER --> CLASSIFY[Classify each question - Analyzer.classify_question]
    CLASSIFY --> |For each teacher message| LLM[OpenAI Responses API<br/>Classify into framework labels]
    LLM --> QA[Save QuestionAnalysis - label + confidence]
    QA --> DIST[Calculate distribution - Count per label]
    DIST --> SUMM[Create SessionSummary - distribution_json + feedback]
    SUMM --> DONE[Return analysis result]

    CLASSIFY --> |Error| FB[create_fallback_summary - Uniform distribution]
    FB --> DONE

    style START fill:#e1f5fe
    style DONE fill:#e8f5e9
    style FB fill:#fff3e0
```

**Framework Labels Example** (High/Low Leverage):
- Pressing (for reasoning)
- Linking (to prior knowledge)
- Directing (closed questions)
- Recall (factual recall)

---

## 6. Tutor Intervention Decision Flow

```mermaid
flowchart TD
    START[Teacher message processed] --> CHECK{Tutor enabled?}
    CHECK -->|No| SKIP[No intervention]
    CHECK -->|Yes| RATE{Within rate limit?<br/>threshold/10 questions}

    RATE -->|Over limit| SKIP
    RATE -->|OK| PAT[Pattern Analysis]

    PAT --> P1{Low-leverage patterns?<br/>yes/no questions, short questions}
    PAT --> P2{Vague patterns?<br/>repetitive phrases}
    PAT --> P3{Repetitive dialogue?<br/>Jaccard similarity > 0.8}

    P1 -->|Detected| INTERVENE[Generate Feedback]
    P2 -->|Detected| INTERVENE
    P3 -->|Detected| INTERVENE

    P1 -->|Not detected| LLMCHECK
    P2 -->|Not detected| LLMCHECK
    P3 -->|Not detected| LLMCHECK

    LLMCHECK{LLM semantic analysis needed?} -->|Yes| LLM[analyze_conversation_with_llm]
    LLM -->|Should intervene| INTERVENE
    LLM -->|OK| SKIP
    LLMCHECK -->|No patterns| SKIP

    INTERVENE --> SAVE[Save tutor Message role=tutor]

    style INTERVENE fill:#fff9c4
    style SKIP fill:#e8f5e9
```

---

## 7. Data Model (Entity Relationship)

```mermaid
erDiagram
    UserGroup ||--o{ User : "has members"
    UserGroup ||--o{ ScenarioGroup : "accesses"

    User ||--o{ Session : "creates as teacher"
    User ||--o{ Scenario : "creates"
    User ||--o{ PromptTemplate : "updates"

    AnalysisFramework ||--o{ Scenario : "categorizes"

    Scenario ||--o{ Session : "has"
    Scenario ||--o{ ScenarioGroup : "assigned to"
    Scenario }o--|| PromptTemplate : "student_template"
    Scenario }o--o| PromptTemplate : "tutor_template"

    Session ||--o{ Message : "contains"
    Session ||--o| SessionSummary : "has"
    Session ||--o{ ApiUsageLog : "tracks"

    Message ||--o| QuestionAnalysis : "analyzed as"

    UserGroup {
        int id PK
        string name UK
        string description
    }

    User {
        int id PK
        string username UK
        string nickname
        string password_hash
        string role
        int group_id FK
    }

    Scenario {
        int id PK
        string title
        text prompt
        text student_profile
        string video_url
        text video_transcript
        int is_active
        int framework_id FK
        int student_template_id FK
        int tutor_template_id FK
        int created_by FK
        datetime deleted_at
    }

    ScenarioGroup {
        int id PK
        int scenario_id FK
        int group_id FK
    }

    AnalysisFramework {
        int id PK
        string name UK
        string description
        text labels_json
    }

    Session {
        int id PK
        int scenario_id FK
        int teacher_id FK
        datetime started_at
        datetime ended_at
        datetime deleted_at
    }

    Message {
        int id PK
        int session_id FK
        string role
        text content
        text analysis_metadata
        datetime created_at
    }

    QuestionAnalysis {
        int id PK
        int message_id FK
        string label
        float confidence
        text meta_json
    }

    SessionSummary {
        int id PK
        int session_id FK
        text distribution_json
        text feedback
    }

    PromptTemplate {
        int id PK
        string bot_type
        string template_name
        text template_text
        int version
        int updated_by FK
    }

    ApiUsageLog {
        int id PK
        int session_id FK
        string bot_type
        string model
        int prompt_tokens
        int completion_tokens
        float estimated_cost_usd
    }
```

---

## 8. Admin Panel Flow

```mermaid
flowchart LR
    ADMIN[Admin Dashboard<br/>GET /admin] --> USERS[Users<br/>/admin/users]
    ADMIN --> GROUPS[Groups<br/>/admin/groups]
    ADMIN --> SCENARIOS[Scenarios<br/>/admin/scenarios]
    ADMIN --> FRAMEWORKS[Frameworks<br/>/admin/frameworks]
    ADMIN --> SESSIONS[Sessions<br/>/admin/sessions-page]
    ADMIN --> PROMPTS[Prompts<br/>/admin/prompts-page]
    ADMIN --> ANALYSIS[Analysis<br/>/admin/analysis-page]
    ADMIN --> API_USAGE[API Usage<br/>/admin/api-usage]

    USERS --> U_OPS["POST Create<br/>PUT Update<br/>DELETE Remove"]
    GROUPS --> G_OPS["POST Create<br/>PUT Update<br/>DELETE Remove"]
    SCENARIOS --> S_OPS["POST Create<br/>PUT Update<br/>DELETE Soft-delete"]
    FRAMEWORKS --> F_OPS["POST Create<br/>PUT Update<br/>DELETE Remove"]
    SESSIONS --> SS_OPS["POST End<br/>DELETE Soft-delete<br/>GET Export CSV"]
    PROMPTS --> P_OPS["POST Create<br/>PUT Update<br/>DELETE Remove"]
```

---

## 9. Group-Based Access Control

```mermaid
flowchart TD
    LOGIN[User logs in] --> ROLE{Role?}

    ROLE -->|admin| ADMIN_VIEW[See ALL scenarios + Full admin panel]
    ROLE -->|teacher| GROUP_CHECK[Check user.group_id]

    GROUP_CHECK --> SG[Query ScenarioGroup<br/>WHERE group_id = user.group_id]
    SG --> FILTERED[Show only assigned scenarios]

    ADMIN_VIEW --> FULL[Full CRUD access]
    FILTERED --> CHAT[Can chat with assigned scenarios only]

    style ADMIN_VIEW fill:#e1f5fe
    style FILTERED fill:#fff9c4
```

**Access Rules**:
- **Admin**: Full access to all scenarios and admin panel
- **Teacher**: Can only see scenarios assigned to their group via ScenarioGroup join table
- **No group assigned**: Teacher sees no scenarios

---

## 10. Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTMX + Vanilla JS + Jinja2 Templates |
| Styling | Custom CSS (CSS Variables) |
| Web Framework | FastAPI (async) |
| ORM | SQLAlchemy 2.x (async) |
| Database | SQLite3 (WAL mode) |
| Auth | Starlette SessionMiddleware + bcrypt |
| Security | CSRF (Double Submit Cookie) + CSP |
| AI/LLM | OpenAI Responses API (GPT-5 family) |
| Rate Limiting | slowapi (5-30 req/min per endpoint) |
| Retry | tenacity (3 attempts, exp backoff) |
| Logging | Structured JSON (stdlib logging) |
| Package Mgmt | uv |

---

## 11. Key Service Dependencies

```mermaid
flowchart TD
    SM[SessionManager] --> SB[StudentBot]
    SM --> TB[TutorBot]
    SM --> MA[MisconceptionAnalyzer]
    SM --> PM[PromptManager]

    SB --> BASE[OpenAIBaseService]
    TB --> BASE
    MA --> BASE
    BASE --> OPENAI[OpenAI API Client]

    SB --> PM
    TB --> PM
    TB --> DA[dialogue_analysis<br/>Pattern Detection]

    AP[analysis_pipeline] --> AZ[Analyzer]
    AZ --> BASE

    PM --> DB[(SQLite)]
    SM --> DB

    EX[CSVExporter] --> DB

    style SM fill:#e1f5fe
    style BASE fill:#fff9c4
    style DB fill:#e8f5e9
```

---

## 12. File Structure Summary

```
src/
  main.py                       # App entry, middleware, lifespan
  config.py                     # Environment config (Pydantic)
  models/
    user.py                     # User (teacher/admin)
    user_group.py               # UserGroup
    scenario.py                 # Scenario (with template FKs)
    scenario_group.py           # ScenarioGroup (join table)
    analysis_framework.py       # AnalysisFramework (labels)
    session.py                  # Session (dialogue session)
    message.py                  # Message (teacher/student/tutor)
    question_analysis.py        # QuestionAnalysis (per-question)
    session_summary.py          # SessionSummary (distribution)
    prompt_template.py          # PromptTemplate (student/tutor)
    api_usage.py                # ApiUsageLog (token tracking)
  services/
    base.py                     # OpenAI base with retry
    student_bot.py              # Student persona bot
    tutor_bot.py                # Tutor intervention bot
    misconception_analyzer.py   # Misconception strength check
    session_mgr.py              # Dialogue orchestration
    analyzer.py                 # Question classification
    analysis_pipeline.py        # Full analysis workflow
    dialogue_analysis.py        # Pattern detection utils
    prompt_manager.py           # Template CRUD
    export.py                   # CSV export (anonymized)
  api/
    dependencies.py             # Auth dependencies
    schemas.py                  # Pydantic request/response models
    routes/
      auth.py                   # Login/Logout
      health.py                 # Health/Metrics
      scenarios.py              # Scenario listing/access
      sessions.py               # Session create/close
      session_messages.py       # Message send/poll
      session_analysis.py       # Analysis trigger/view
      admin.py                  # Admin dashboard
      admin_users.py            # User CRUD
      admin_groups.py           # Group CRUD
      admin_scenarios.py        # Scenario CRUD
      admin_frameworks.py       # Framework CRUD
      admin_sessions.py         # Session listing
      admin_session_actions.py  # Session end/delete/detail
      admin_session_export.py   # CSV export
      admin_session_stats.py    # Statistics
      admin_analysis.py         # Analysis management
      admin_api_usage.py        # API usage dashboard
      admin_prompts.py          # Prompt CRUD
  db/
    connection.py               # Async engine + session factory
    init_schema.py              # DDL schema
    seed.py                     # Default data seeding
    migrations/                 # SQL migrations (001-007)
  templates/                    # Jinja2 HTML templates
  prompts/                      # Default prompt text files
```

---

## 13. API Endpoints Summary

| Method | Path | Rate | Auth | Description |
|--------|------|------|------|-------------|
| GET | /login | - | No | Login page |
| POST | /login | 5/min | No | Authenticate |
| POST | /logout | - | Yes | Clear session |
| GET | /scenarios | - | Yes | List scenarios |
| GET | /scenarios/{id} | - | Yes | Enter scenario + create session |
| POST | /sessions | 10/min | Yes | Create session (JSON) |
| POST | /sessions/{id}/messages | 30/min | Yes | Send message |
| GET | /sessions/{id}/messages/updates | - | Yes | Poll new messages |
| POST | /sessions/{id}/end | 10/min | Yes | End session |
| POST | /sessions/{id}/close | 30/min | Yes | Close session (idempotent) |
| POST | /sessions/{id}/analyze | 5/min | Yes | Run analysis |
| GET | /sessions/{id}/analysis | - | Yes | Get analysis JSON |
| GET | /sessions/{id}/analysis_page | - | Yes | Analysis page |
| GET | /sessions/{id}/analysis_modal | - | Yes | Analysis modal (HTMX) |
| GET | /sessions/{id}/export.csv | - | Yes | Export CSV |
| GET | /health | - | No | Health check |
| GET | /metrics | - | No | System metrics |
| GET | /admin | - | Admin | Dashboard |
| GET/POST | /admin/users | - | Admin | List/Create users |
| PUT/DELETE | /admin/users/{id} | - | Admin | Update/Delete user |
| GET/POST | /admin/groups | - | Admin | List/Create groups |
| PUT/DELETE | /admin/groups/{id} | - | Admin | Update/Delete group |
| GET/POST | /admin/scenarios | - | Admin | List/Create scenarios |
| PUT/DELETE | /admin/scenarios/{id} | - | Admin | Update/Delete scenario |
| GET/POST | /admin/frameworks | - | Admin | List/Create frameworks |
| PUT/DELETE | /admin/frameworks/{id} | - | Admin | Update/Delete framework |
| GET/POST | /admin/prompts | - | Admin | List/Create prompts |
| PUT/DELETE | /admin/prompts/{id} | - | Admin | Update/Delete prompt |
| GET | /admin/sessions-page | - | Admin | Session logs |
| GET | /admin/sessions/export | - | Admin | Export sessions CSV |
| GET | /admin/analysis-page | - | Admin | Analysis management |
| GET | /admin/api-usage | - | Admin | API usage dashboard |
| GET | /admin/stats | - | Admin | System statistics |
