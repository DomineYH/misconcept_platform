# Dialogue Coaching Badge Rename Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 분석 보고서의 `대화코칭` 영역에서 low-grade 교사 발화에 표시되는 `놓친 순간` 배지를 `개선 필요`로 변경한다.

**Architecture:** 변경 범위는 공용 partial인 `src/templates/partials/analysis_detail_tabs.html`의 대화코칭 타임라인 배지 문구 한 곳이다. `잘 한 대화` 배지, `우수한 점`/`개선할 점` 탭 라벨, 저장 등급값(`우수`, `개선`), API JSON 키(`strengths`, `improvements`)는 변경하지 않는다.

**Tech Stack:** FastAPI, Jinja2 templates, pytest, server-rendered analysis modal/page.

---

## Assumptions

- GitHub Issue #51 is the product scope for this change.
- `대화 코딩` in any discussion of this issue refers to the existing `대화코칭` UI area.
- `잘 한 대화` is already the desired high-grade teacher badge copy and remains unchanged.
- The only visible copy change is the low-grade teacher badge in the `대화코칭` timeline.
- Detailed analysis tab labels `우수한 점` and `개선할 점` stay unchanged.

## File Map

- Modify: `src/templates/partials/analysis_detail_tabs.html`
  - Change the badge text rendered when `m.role == 'teacher' and m.level == 'low'`.
- Modify: `tests/integration/test_analysis_modal_tabs.py`
  - Verify the real analysis modal HTML keeps `잘 한 대화`, shows `개선 필요`, and no longer shows `놓친 순간`.
- Modify: `tests/templates/test_analysis_modal_states.py`
  - Verify template-level rendering of the shared analysis modal uses the requested badge labels.

## Task 1: Failing Tests For The 대화코칭 Badge Copy

**Files:**
- Modify: `tests/integration/test_analysis_modal_tabs.py`
- Modify: `tests/templates/test_analysis_modal_states.py`

- [ ] **Step 1: Add an integration assertion for dialogue coaching badges**

In `tests/integration/test_analysis_modal_tabs.py`, add this focused test after `test_analysis_modal_renders_three_tabs`:

```python
async def test_analysis_modal_uses_requested_dialogue_coaching_badges(
    test_client: TestClient,
    seeded_analyzed_session: Session,
):
    """대화코칭 배지는 잘 한 대화/개선 필요 문구를 사용한다."""
    cookies = _login(test_client)
    resp = test_client.get(
        f"/sessions/{seeded_analyzed_session.id}/analysis_modal",
        cookies=cookies,
    )
    assert resp.status_code == 200
    html = resp.text

    assert "잘 한 대화" in html
    assert "개선 필요" in html
    assert "놓친 순간" not in html
```

- [ ] **Step 2: Add a template-level regression assertion**

In `tests/templates/test_analysis_modal_states.py`, add this test in `TestOkState`:

```python
    def test_dialogue_coaching_badges_use_requested_labels(self, env):
        template = env.get_template("partials/analysis_modal.html")
        ctx = _ok_context()
        ctx["messages"] = [
            {
                "role": "teacher",
                "content": "왜 그렇게 생각하니?",
                "level": "high",
            },
            {
                "role": "teacher",
                "content": "정답이 뭐였더라?",
                "level": "low",
            },
        ]
        html = template.render(**ctx)

        assert "잘 한 대화" in html
        assert "개선 필요" in html
        assert "놓친 순간" not in html
```

- [ ] **Step 3: Run the focused tests and verify they fail before implementation**

Run:

```bash
PYTHONPATH=. uv run pytest tests/integration/test_analysis_modal_tabs.py::test_analysis_modal_uses_requested_dialogue_coaching_badges tests/templates/test_analysis_modal_states.py::TestOkState::test_dialogue_coaching_badges_use_requested_labels -v
```

Expected: FAIL because current UI still renders `놓친 순간` for low-grade teacher messages.

## Task 2: Rename Only The Low-Grade 대화코칭 Badge

**Files:**
- Modify: `src/templates/partials/analysis_detail_tabs.html`

- [ ] **Step 1: Update the low-grade teacher badge copy**

In `src/templates/partials/analysis_detail_tabs.html`, change only this visible text inside the `m.role == 'teacher' and m.level == 'low'` branch:

```diff
- <span class="coach-msg__tag tag--bad">놓친 순간</span>
+ <span class="coach-msg__tag tag--bad">개선 필요</span>
```

Do not change:

```html
<span class="coach-msg__tag tag--good">잘 한 대화</span>
```

Do not rename element IDs such as `tab-strong`, `tab-improve`, `panel-strong`, or `panel-improve`.

Do not change the tab labels:

```text
우수한 점
개선할 점
```

- [ ] **Step 2: Run the focused tests again**

Run:

```bash
PYTHONPATH=. uv run pytest tests/integration/test_analysis_modal_tabs.py::test_analysis_modal_uses_requested_dialogue_coaching_badges tests/templates/test_analysis_modal_states.py::TestOkState::test_dialogue_coaching_badges_use_requested_labels -v
```

Expected: PASS.

## Task 3: Verify The Shared Analysis Report Surfaces

**Files:**
- Verify: `src/templates/analysis.html`
- Verify: `src/templates/partials/analysis_modal.html`
- Test: `tests/integration/test_analysis_modal_tabs.py`
- Test: `tests/templates/test_analysis_modal_states.py`

- [ ] **Step 1: Run existing analysis tab integration tests**

Run:

```bash
PYTHONPATH=. uv run pytest tests/integration/test_analysis_modal_tabs.py -v
```

Expected: all tests PASS.

- [ ] **Step 2: Run modal state template tests**

Run:

```bash
PYTHONPATH=. uv run pytest tests/templates/test_analysis_modal_states.py -v
```

Expected: all tests PASS.

- [ ] **Step 3: Search the active analysis report UI for the old badge copy**

Run:

```bash
rg -n "놓친 순간" src/templates/partials/analysis_detail_tabs.html tests/integration/test_analysis_modal_tabs.py tests/templates/test_analysis_modal_states.py
```

Expected: no matches.

## Acceptance Criteria

- `대화코칭` 타임라인에서 high-grade teacher message 배지는 계속 `잘 한 대화`로 보인다.
- `대화코칭` 타임라인에서 low-grade teacher message 배지는 `놓친 순간` 대신 `개선 필요`로 보인다.
- 상세 분석 탭 라벨 `우수한 점`과 `개선할 점`은 그대로 유지된다.
- 저장 데이터값, API 응답 키, DOM ID, JavaScript 동작은 변경하지 않는다.
- teacher/admin 분석 모달과 전체 분석 페이지 모두 공용 partial을 통해 동일한 배지 문구를 사용한다.

## Verification

Run:

```bash
PYTHONPATH=. uv run pytest tests/integration/test_analysis_modal_tabs.py -v
PYTHONPATH=. uv run pytest tests/templates/test_analysis_modal_states.py -v
rg -n "놓친 순간" src/templates/partials/analysis_detail_tabs.html tests/integration/test_analysis_modal_tabs.py tests/templates/test_analysis_modal_states.py
```
