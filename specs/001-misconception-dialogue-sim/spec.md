# Feature Specification: Misconception Dialogue Simulator

**Feature Branch**: `001-misconception-dialogue-sim`
**Created**: 2025-11-05
**Status**: Phase 6 Complete (74.1%)
**Input**: User description: "@docs/prd.md"
**Progress**: 83/112 tasks | Phase 7 Ready

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Teacher Conducts Dialogue Session (Priority: P1)

A teacher selects a pre-defined scenario, engages in dialogue with
the student chatbot, and receives real-time feedback when the tutor
chatbot intervenes to guide the conversation quality.

**Why this priority**: Core value proposition - enables teachers to
practice pedagogical questioning techniques in a safe, simulated
environment with immediate feedback.

**Independent Test**: Can be fully tested by having a teacher log in,
select any active scenario, conduct a multi-turn dialogue where at
least one low-leverage question triggers tutor intervention, and
observe the three-party interaction flow.

**Acceptance Scenarios**:

1. **Given** teacher has logged in with student ID and nickname,
   **When** teacher selects an active scenario from the list,
   **Then** dialogue interface displays with student chatbot ready
   to respond according to the scenario's misconception profile
2. **Given** teacher is in an active dialogue session,
   **When** teacher asks a question to the student chatbot,
   **Then** student chatbot responds within 2 seconds showing behavior
   consistent with the defined misconception
3. **Given** teacher asks multiple low-leverage questions,
   **When** tutor detection threshold is reached,
   **Then** tutor chatbot intervenes with specific feedback suggesting
   higher-leverage alternatives
4. **Given** teacher asks conceptually-focused questions repeatedly,
   **When** student chatbot's understanding threshold is met,
   **Then** student chatbot demonstrates progressive insight or "aha
   moment" response

---

### User Story 2 - Teacher Reviews Session Analysis (Priority: P2)

After completing a dialogue session, teacher views a detailed analysis
report showing question type classification (high/low leverage),
frequency statistics, and personalized feedback, then downloads the
report as CSV.

**Why this priority**: Critical for reflective practice - teachers need
to understand their pedagogical patterns to improve questioning
strategies.

**Independent Test**: Can be tested independently by completing any
dialogue session, triggering the session end, viewing the analysis
report with question classification badges and frequency charts, and
successfully downloading the CSV file.

**Acceptance Scenarios**:

1. **Given** teacher has completed a dialogue session,
   **When** teacher ends the session,
   **Then** system displays analysis report showing all questions with
   type badges (high/low leverage)
2. **Given** analysis report is displayed,
   **When** teacher views the frequency section,
   **Then** bar chart visualization shows distribution of question
   types with percentage breakdown
3. **Given** analysis report is displayed,
   **When** teacher clicks download CSV button,
   **Then** CSV file downloads containing timestamped questions,
   classifications, and anonymized session identifier
4. **Given** analysis report shows predominantly low-leverage questions,
   **When** teacher views summary feedback,
   **Then** system provides specific suggestions for improving
   question quality

---

### User Story 3 - Admin Manages Scenarios (Priority: P3)

Administrator creates, edits, and activates/deactivates dialogue
scenarios, each defining the student's misconception profile, problem
context, and student characteristics.

**Why this priority**: Enables content management and customization
for different pedagogical contexts, but core teacher experience works
with any existing scenario.

**Independent Test**: Can be tested by admin logging in, creating a
new scenario with misconception details and problem context,
activating it, and verifying it appears in teacher's scenario list.

**Acceptance Scenarios**:

1. **Given** admin is logged into admin panel,
   **When** admin creates a new scenario with misconception description
   and problem context,
   **Then** scenario is saved and appears in scenario management list
2. **Given** admin views scenario list,
   **When** admin toggles a scenario's active status,
   **Then** scenario visibility changes in teacher's scenario selection
   interface accordingly
3. **Given** admin is editing an existing scenario,
   **When** admin modifies misconception profile or student
   characteristics,
   **Then** changes are saved and reflected immediately in new dialogue
   sessions using that scenario
4. **Given** admin is creating a scenario,
   **When** admin leaves required fields empty,
   **Then** system prevents saving and highlights missing information

---

### User Story 4 - Admin Configures Analysis Framework (Priority: P4)

Administrator selects and applies an analysis framework (pedagogical
move classification system) that defines how questions are categorized
and what constitutes high vs. low leverage moves.

**Why this priority**: Allows customization of analysis criteria for
different educational contexts and research frameworks, but default
framework enables immediate use.

**Independent Test**: Can be tested by admin selecting an alternative
analysis framework from pre-registered options, applying it, and
verifying subsequent sessions use the new classification scheme.

**Acceptance Scenarios**:

1. **Given** admin views analysis framework settings,
   **When** admin selects a different framework from available options,
   **Then** system applies new classification rules to future sessions
2. **Given** admin has applied a new framework,
   **When** teacher completes a session,
   **Then** analysis report uses the newly selected framework's
   categories and criteria
3. **Given** multiple frameworks are registered,
   **When** admin views framework list,
   **Then** each framework shows name, description, and category
   definitions

---

### User Story 5 - Admin Reviews Session Logs (Priority: P5)

Administrator views aggregated statistics across all sessions,
searches/filters session logs, and downloads CSV exports for research
or quality monitoring purposes.

**Why this priority**: Supports research and quality assurance but not
essential for core teacher training functionality.

**Independent Test**: Can be tested by admin accessing session log
dashboard, applying date range and user filters, viewing aggregated
metrics, and downloading filtered results as CSV.

**Acceptance Scenarios**:

1. **Given** admin accesses session log dashboard,
   **When** admin applies date range filter,
   **Then** dashboard shows only sessions within specified timeframe
2. **Given** admin views session statistics,
   **When** dashboard loads,
   **Then** aggregate metrics show total sessions, average question
   counts, leverage ratio distributions
3. **Given** admin has filtered session list,
   **When** admin clicks export CSV button,
   **Then** CSV downloads with anonymized identifiers and full
   dialogue transcripts

---

### Edge Cases

- What happens when student chatbot fails to respond within timeout?
  → System displays error message and offers retry or session save
- What happens when tutor chatbot intervenes excessively (multiple
  times in short window)? → Tutor intervention is rate-limited to avoid
  overwhelming teacher, maximum 3 interventions per 10 questions
- What happens when teacher session is interrupted (network loss,
  browser close)? → Session state is auto-saved every 30 seconds;
  teacher can resume from last saved state
- What happens when multiple teachers attempt concurrent sessions with
  same scenario? → Each session operates independently with no
  resource conflicts
- What happens when analysis framework cannot classify a question?
  → Question is marked as "uncategorized" and flagged for admin review
- What happens when CSV download fails? → System provides alternate
  download link and offers in-browser view as fallback
- What happens when admin deactivates a scenario mid-session?
  → Active sessions continue unaffected; new sessions cannot select
  the deactivated scenario
- What happens when student chatbot reaches "aha moment" but teacher
  continues asking questions? → Student maintains new understanding
  level, responses reflect corrected conceptual model

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide three-party dialogue interface
  displaying messages from teacher, student chatbot, and tutor chatbot
  with distinct visual labels
- **FR-002**: System MUST timestamp every message in dialogue log
  with precision to the second
- **FR-003**: System MUST allow admin to create scenarios including
  misconception description, student characteristics, problem context,
  and activation toggle
- **FR-004**: System MUST allow admin to select from pre-registered
  analysis frameworks for pedagogical move classification
- **FR-005**: System MUST classify teacher questions according to
  selected analysis framework (default: high/low leverage categories)
- **FR-006**: System MUST trigger tutor chatbot intervention when
  dialogue quality thresholds are met (stagnation, derailment, or
  excessive low-leverage questions)
- **FR-007**: System MUST allow student chatbot to demonstrate
  progressive understanding when conceptual question threshold is
  reached
- **FR-008**: System MUST generate post-session analysis report
  showing question list with type badges, frequency bar charts, and
  summary feedback
- **FR-009**: System MUST export session data to CSV format including
  timestamps, question text, classifications, and anonymized session
  identifier
- **FR-010**: System MUST authenticate users with student ID and
  nickname fields only (minimal personal information)
- **FR-011**: System MUST maintain session state and support auto-save
  every 30 seconds to enable resumption after interruption
- **FR-012**: System MUST respond to teacher questions within 2 seconds
  average latency
- **FR-013**: System MUST support 100 concurrent dialogue sessions
  without performance degradation
- **FR-014**: Admin MUST be able to view aggregated session statistics
  and search/filter session logs by date range and user
- **FR-015**: System MUST log all admin actions (scenario changes,
  framework selections) for audit trail
- **FR-016**: System MUST allow teacher to end session at any point
  and view analysis report immediately
- **FR-017**: System MUST prevent modification or deletion of active
  scenarios currently in use by teachers
- **FR-018**: System MUST display only active scenarios in teacher's
  scenario selection list
- **FR-019**: Tutor chatbot interventions MUST include specific
  alternative question suggestions or positive reinforcement feedback
- **FR-020**: Student chatbot responses MUST remain consistent with
  defined misconception profile until understanding threshold is met

### Key Entities

- **Scenario**: Represents a dialogue situation; includes misconception
  description, student characteristics, problem context, active status;
  created and managed by admin
- **Session**: Represents one teacher-student dialogue instance;
  contains scenario reference, timestamp, participant messages, current
  state (active/completed); linked to specific teacher identifier
- **Message**: Individual dialogue turn; includes speaker role
  (teacher/student/tutor), timestamp, text content, classification
  (if teacher question); belongs to one session
- **Analysis Framework**: Classification system for pedagogical moves;
  includes framework name, category definitions (e.g., high/low
  leverage), classification rules; selected by admin
- **Pedagogical Move**: Classified teacher question; includes question
  text, assigned category (high/low leverage or other framework-
  specific type), timestamp; analyzed according to selected framework
- **User**: Teacher or admin; includes anonymous identifier (student
  ID), nickname, role; minimal personal information stored
- **Session Report**: Analysis output; includes question list with
  classifications, frequency statistics, visual charts, summary
  feedback; generated at session end

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Teachers complete at least 80% of started dialogue
  sessions (session completion rate)
- **SC-002**: Average session duration is between 10-20 minutes for
  typical scenario (indicates engagement without excessive length)
- **SC-003**: High-leverage question ratio increases by 30% between
  teacher's first and fifth session (demonstrates learning)
- **SC-004**: Student chatbot reaches "aha moment" in at least 60% of
  completed sessions (indicates effective conceptual guidance)
- **SC-005**: System maintains average response latency under 2 seconds
  for 95% of questions
- **SC-006**: System supports 100 concurrent sessions without exceeding
  3-second response time for any message
- **SC-007**: Teachers download CSV analysis report for at least 50% of
  completed sessions (indicates value of reflective analysis)
- **SC-008**: Tutor intervention rate stabilizes below 20% of questions
  after teacher's third session (indicates improving question quality)
- **SC-009**: Teachers revisit platform for multiple sessions with
  70%+ return rate within one week (indicates sustained engagement)
- **SC-010**: Admin creates at least 5 distinct scenarios covering
  different misconception types within first month (content variety)

### Assumptions

- Teachers have basic web browser access and internet connectivity
- Default analysis framework (high/low leverage pedagogical moves)
  is sufficient for initial release
- Teachers require no formal training to understand dialogue interface
  and analysis reports
- Student ID and nickname provide sufficient identification without
  requiring email or stronger authentication
- Average dialogue consists of 15-25 question turns from teacher
- Sessions do not require real-time video or audio, text-only
  interaction is sufficient
- Admin population is small (1-5 users) and does not require complex
  role-based permissions
- CSV export format follows standard conventions (UTF-8, comma-
  delimited, quoted fields)
- Chatbot responses are generated using external LLM API with adequate
  rate limits and reliability
- Session data retention follows institution's standard practices
  (typically 1-2 years for educational records)
