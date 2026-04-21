# Design System — Misconception Dialogue Simulator

> Single source of truth for the visual design system. Every token declared in `static/css/styles.css` is documented here with its role, usage rules, and (for color pairs) WCAG AA contrast evidence.
>
> **Before making any visual or UI change, read this document.** If a change would introduce a new token, update this document in the same PR.

---

## Product Context

- **What this is:** A three-party dialogue simulator for teacher training. Teachers practice pedagogical questioning against AI student chatbots that exhibit misconceptions, while AI tutor chatbots provide real-time feedback.
- **Who it's for:** Pre-service and in-service teachers, teacher trainers, education researchers.
- **Project type:** Server-rendered web app (FastAPI + Jinja2 + SQLite). Used in classroom and training contexts.
- **Stakes:** The interface must stay out of the way. The content — dialogue, feedback, misconception analysis — is the product.

## Aesthetic Direction

- **Direction:** Musinsa-inspired monochrome minimalism. Black, white, grays. Restraint as the default.
- **Decoration level:** Minimal. Typography and whitespace do the work. No gradients, no decorative blobs, no purple accents.
- **Layout approach:** Grid-disciplined. Max content width caps at 1400px (see `header nav` in `styles.css`).
- **Color approach:** Restrained. The monochrome palette carries hierarchy. Semantic color (success/warning/danger/info) only when it aids comprehension. Role-based message colors only for chat bubbles.
- **Motion:** Minimal-functional. Three transition speeds (`--transition-fast/normal/slow`), ease curves.
- **Why this fits:** Teachers and trainers are the users. In a training session, cognitive load belongs to the dialogue content, not the chrome. A loud UI would compete with the misconception analysis it's meant to expose.

Explicit departures from common SaaS defaults: no brand accent color, no gradient CTAs, no bubbly radius. `--color-primary` is `#000000`.

---

## Color System

Every color token declared in `static/css/styles.css` under `:root` (lines 9-116) and `@media (prefers-color-scheme: dark) { :root { ... } }` (lines 2971-3035) is listed below. The tables are the authoritative mapping; the script at the end of this document enforces 100% coverage.

### Primary Colors — Monochrome

Light:

| Token | Value | Usage |
|-------|-------|-------|
| `--color-black` | `#000000` | Primary text, primary button background, focus outline. |
| `--color-white` | `#FFFFFF` | Page background, card surface, teacher message bubble. |
| `--color-gray-50` | `#FAFAFA` | Very subtle background (secondary surface). |
| `--color-gray-100` | `#F5F5F5` | Tertiary background, disabled surface. |
| `--color-gray-200` | `#EEEEEE` | Light border. |
| `--color-gray-300` | `#E0E0E0` | Medium border. |
| `--color-gray-400` | `#BDBDBD` | Muted text (decorative only — fails AA). |
| `--color-gray-500` | `#9E9E9E` | Tertiary text on white (fails AA — captions/timestamps only). |
| `--color-gray-600` | `#757575` | — (reserved; not currently bound to a semantic token). |
| `--color-gray-700` | `#616161` | — (reserved). |
| `--color-gray-800` | `#424242` | — (reserved). |
| `--color-gray-900` | `#212121` | — (reserved). |

Dark (overrides):

| Token | Value | Note |
|-------|-------|------|
| `--color-black` | `#FFFFFF` | Inverted. "Black" now paints white text/icons. |
| `--color-white` | `#0A0A0A` | Inverted. "White" now paints the dark canvas. |
| `--color-gray-50` | `#121212` | |
| `--color-gray-100` | `#1A1A1A` | |
| `--color-gray-200` | `#2A2A2A` | |
| `--color-gray-300` | `#3A3A3A` | |
| `--color-gray-400` | `#4A4A4A` | |
| `--color-gray-500` | `#6A6A6A` | |
| `--color-gray-600` | `#8A8A8A` | |
| `--color-gray-700` | `#AAAAAA` | |
| `--color-gray-800` | `#CACACA` | |
| `--color-gray-900` | `#EAEAEA` | |

### Semantic Colors

Light:

| Token | Value | Usage |
|-------|-------|-------|
| `--color-primary` | `#000000` | Primary actions (submit, confirm). |
| `--color-primary-hover` | `#333333` | Primary button hover. |
| `--color-secondary` | `#FFFFFF` | Secondary surface. |
| `--color-accent` | `#000000` | Emphasis (same as primary — no brand accent by design). |

Dark:

| Token | Value |
|-------|-------|
| `--color-primary` | `#FFFFFF` |
| `--color-primary-hover` | `#CCCCCC` |

(`--color-secondary` and `--color-accent` are not overridden in dark — they inherit from the redefined `--color-white` / `--color-black`.)

### Text Colors

Light:

| Token | Value | Usage |
|-------|-------|-------|
| `--color-text-primary` | `#000000` | Body copy, headings. |
| `--color-text-secondary` | `#666666` | Subtitles, supporting copy. |
| `--color-text-tertiary` | `#999999` | Timestamps, captions. **Fails AA — use ≥18px or bold.** |
| `--color-text-muted` | `#BDBDBD` | Disabled text / placeholder only. **Fails AA.** |

Dark:

| Token | Value |
|-------|-------|
| `--color-text-primary` | `#FFFFFF` |
| `--color-text-secondary` | `#AAAAAA` |
| `--color-text-tertiary` | `#777777` |
| `--color-text-muted` | `#555555` |

### Background Colors

Light:

| Token | Value | Usage |
|-------|-------|-------|
| `--color-bg-body` | `#FFFFFF` | Page background. |
| `--color-bg-surface` | `#FFFFFF` | Card / panel surface. Same as body in light to keep surfaces flat. |
| `--color-bg-secondary` | `#FAFAFA` | Alternate row, section backdrop. |
| `--color-bg-tertiary` | `#F5F5F5` | Pressed / input backdrop. |

Dark:

| Token | Value |
|-------|-------|
| `--color-bg-body` | `#0A0A0A` |
| `--color-bg-surface` | `#0A0A0A` |
| `--color-bg-secondary` | `#121212` |
| `--color-bg-tertiary` | `#1A1A1A` |

### Border Colors

Light:

| Token | Value | Usage |
|-------|-------|-------|
| `--color-border-light` | `#EEEEEE` | Default border, subtle divider. |
| `--color-border-medium` | `#E0E0E0` | Form input border. |
| `--color-border-dark` | `#BDBDBD` | Emphasized border, table header. |

Dark:

| Token | Value |
|-------|-------|
| `--color-border-light` | `#2A2A2A` |
| `--color-border-medium` | `#3A3A3A` |
| `--color-border-dark` | `#4A4A4A` |

### Role Colors — Subtle

Used for role labels, sidebar markers, and non-message role chrome. NOT for message bubbles (see next section for those).

Light:

| Token | Value | Usage |
|-------|-------|-------|
| `--color-student` | `#333333` | Student role label. |
| `--color-teacher` | `#000000` | Teacher role label. |
| `--color-tutor` | `#666666` | Tutor role label. |
| `--color-tutor-bg` | `#F5F5F5` | Tutor panel background. |
| `--color-tutor-border` | `#E0E0E0` | Tutor panel border. |
| `--color-tutor-text` | `#333333` | Tutor panel text. |

Dark:

| Token | Value |
|-------|-------|
| `--color-student` | `#CCCCCC` |
| `--color-teacher` | `#FFFFFF` |
| `--color-tutor` | `#888888` |
| `--color-tutor-bg` | `#1A1A1A` |
| `--color-tutor-border` | `#3A3A3A` |
| `--color-tutor-text` | `#CCCCCC` |

### Role Colors — Message Bubbles (Student / Mentor)

Added in PR #18 (closes #15). This is the only place blue enters the palette, and only for mentor-authored messages. Student bubbles stay monochrome.

Light:

| Token | Value | Usage |
|-------|-------|-------|
| `--color-student-bg` | `#FFFFFF` | Student message bubble background. |
| `--color-student-border` | `#EEEEEE` | Student message bubble border. |
| `--color-student-text` | `#000000` | Student message text. |
| `--color-mentor-bg` | `#E3F2FD` | Mentor (tutor) message bubble background. |
| `--color-mentor-border` | `#1565C0` | Mentor message bubble border (stronger than student for visual weight). |
| `--color-mentor-text` | `#0D47A1` | Mentor message text. |

Dark:

| Token | Value |
|-------|-------|
| `--color-student-bg` | `#121212` |
| `--color-student-border` | `#2A2A2A` |
| `--color-student-text` | `#FFFFFF` |
| `--color-mentor-bg` | `#1A2A3D` |
| `--color-mentor-border` | `#64B5F6` |
| `--color-mentor-text` | `#BBDEFB` |

#### Role-based Message Usage Rules

Locked in issue #15 / PR #18:

1. **Student bubbles are monochrome.** Always `--color-student-bg/border/text`. Never apply mentor tokens to student messages.
2. **Mentor bubbles carry the blue accent.** This is the only blue allowed outside status (`info`). It signals "expert intervention" visually.
3. **Teacher messages** (the human user) use neutral surface: `background: var(--color-white)`, `color: var(--color-bg-body)` — i.e., a filled "own message" look. No mentor blue.
4. **Tutor panels** (non-message, e.g., sidebar feedback card) use the tutor subtle tokens, not mentor tokens.
5. **Never stack roles.** A single bubble gets exactly one role's token trio (bg, border, text).
6. **New role?** Before adding a token like `--color-coach-*`, open an issue. The role must have a distinct pedagogical meaning, not just a new accent.

### Status Colors

Light:

| Token | Value | Usage |
|-------|-------|-------|
| `--color-success` | `#2E7D32` | Success icon / accent line. |
| `--color-success-text` | `#1B5E20` | Success body text on `--color-success-bg`. |
| `--color-success-bg` | `#E8F5E9` | Success alert background. |
| `--color-success-border` | `#C8E6C9` | Success alert border. |
| `--color-warning` | `#F57C00` | Warning icon / accent line. |
| `--color-warning-text` | `#E65100` | Warning body text. **Body-sized text fails AA on `--color-warning-bg` — use ≥18px or bold.** |
| `--color-warning-bg` | `#FFF3E0` | Warning alert background. |
| `--color-warning-border` | `#FFE0B2` | Warning alert border. |
| `--color-danger` | `#C62828` | Danger icon / accent line. |
| `--color-danger-text` | `#B71C1C` | Danger body text. |
| `--color-danger-bg` | `#FFEBEE` | Danger alert background. |
| `--color-info-text` | `#1565C0` | Info body text. |
| `--color-info-bg` | `#E3F2FD` | Info alert background. |

(`--color-info` and `--color-danger-border` are intentionally absent — if added, document here and update this table in the same PR.)

Dark:

| Token | Value |
|-------|-------|
| `--color-success` | `#4CAF50` |
| `--color-success-text` | `#81C784` |
| `--color-success-bg` | `#1B3D1E` |
| `--color-success-border` | `#2E5A31` |
| `--color-warning` | `#FF9800` |
| `--color-warning-text` | `#FFB74D` |
| `--color-warning-bg` | `#3D2A0A` |
| `--color-warning-border` | `#5A3D0F` |
| `--color-danger` | `#F44336` |
| `--color-danger-text` | `#EF9A9A` |
| `--color-danger-bg` | `#3D1A1A` |
| `--color-info-text` | `#64B5F6` |
| `--color-info-bg` | `#1A2A3D` |

---

## WCAG AA Contrast Verification

Contrast ratios computed per WCAG 2.1 relative-luminance formula. Threshold: **4.5:1 for body text, 3.0:1 for large text (≥18px or ≥14px bold) and graphical elements.** Ratios regenerated by the verification script — do not edit manually.

### Light mode

| Pair | fg | bg | Ratio | AA body (4.5:1) | AA large (3.0:1) |
|------|----|----|-------|-----------------|------------------|
| text-primary / bg-body | `#000000` | `#FFFFFF` | 21.00:1 | ✅ PASS | ✅ PASS |
| text-secondary / bg-body | `#666666` | `#FFFFFF` | 5.74:1 | ✅ PASS | ✅ PASS |
| text-tertiary / bg-body | `#999999` | `#FFFFFF` | 2.85:1 | ❌ FAIL | ❌ FAIL |
| text-muted / bg-body | `#BDBDBD` | `#FFFFFF` | 1.88:1 | ❌ FAIL | ❌ FAIL |
| student-text / student-bg | `#000000` | `#FFFFFF` | 21.00:1 | ✅ PASS | ✅ PASS |
| mentor-text / mentor-bg | `#0D47A1` | `#E3F2FD` | 7.56:1 | ✅ PASS | ✅ PASS |
| tutor-text / tutor-bg | `#333333` | `#F5F5F5` | 11.59:1 | ✅ PASS | ✅ PASS |
| success-text / success-bg | `#1B5E20` | `#E8F5E9` | 7.00:1 | ✅ PASS | ✅ PASS |
| warning-text / warning-bg | `#E65100` | `#FFF3E0` | 3.46:1 | ❌ FAIL | ✅ PASS |
| danger-text / danger-bg | `#B71C1C` | `#FFEBEE` | 5.75:1 | ✅ PASS | ✅ PASS |
| info-text / info-bg | `#1565C0` | `#E3F2FD` | 5.03:1 | ✅ PASS | ✅ PASS |

### Dark mode

| Pair | fg | bg | Ratio | AA body (4.5:1) | AA large (3.0:1) |
|------|----|----|-------|-----------------|------------------|
| text-primary / bg-body | `#FFFFFF` | `#0A0A0A` | 19.80:1 | ✅ PASS | ✅ PASS |
| text-secondary / bg-body | `#AAAAAA` | `#0A0A0A` | 8.52:1 | ✅ PASS | ✅ PASS |
| text-tertiary / bg-body | `#777777` | `#0A0A0A` | 4.42:1 | ❌ FAIL | ✅ PASS |
| text-muted / bg-body | `#555555` | `#0A0A0A` | 2.66:1 | ❌ FAIL | ❌ FAIL |
| student-text / student-bg | `#FFFFFF` | `#121212` | 18.73:1 | ✅ PASS | ✅ PASS |
| mentor-text / mentor-bg | `#BBDEFB` | `#1A2A3D` | 10.37:1 | ✅ PASS | ✅ PASS |
| tutor-text / tutor-bg | `#CCCCCC` | `#1A1A1A` | 10.84:1 | ✅ PASS | ✅ PASS |
| success-text / success-bg | `#81C784` | `#1B3D1E` | 6.02:1 | ✅ PASS | ✅ PASS |
| warning-text / warning-bg | `#FFB74D` | `#3D2A0A` | 7.91:1 | ✅ PASS | ✅ PASS |
| danger-text / danger-bg | `#EF9A9A` | `#3D1A1A` | 7.17:1 | ✅ PASS | ✅ PASS |
| info-text / info-bg | `#64B5F6` | `#1A2A3D` | 6.57:1 | ✅ PASS | ✅ PASS |

### Rules derived from the table

- **`--color-text-tertiary` and `--color-text-muted` are not safe for body text in either mode.** Use for captions (≥18px), timestamps, or disabled states only. Never for primary informational copy.
- **`--color-warning-text` on `--color-warning-bg` fails body AA in light mode.** When building warning alerts, either use ≥18px or ≥14px bold, or pair `--color-warning-text` with `--color-bg-body` (where it passes).
- **All role-based message combinations pass AA body in both modes.**

---

## Typography

| Token | Value | Role |
|-------|-------|------|
| `--font-family` | `'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans KR', sans-serif` | System font stack. Pretendard is the primary Korean-first sans. |
| `--font-size-xs` | `0.75rem` | Captions, timestamps. |
| `--font-size-sm` | `0.875rem` | Labels, meta. |
| `--font-size-base` | `1rem` | Body copy. |
| `--font-size-lg` | `1.125rem` | Emphasized body, subheadings. |
| `--font-size-xl` | `1.25rem` | Section headings (h3-level). |
| `--font-size-2xl` | `1.5rem` | Page headings (h2-level). |
| `--font-size-3xl` | `2rem` | Page title (h1-level). |

- Root font-size is `16px`. All tokens scale off that.
- `body` line-height is `1.6`; letter-spacing is `-0.01em`. These are not tokenized — keep them on `body` only.
- No custom font weights are tokenized. Use native `font-weight: 400/500/600/700` as needed.
- No serif or display face. If a future page needs it, add a `--font-family-display` token and document here first.

---

## Spacing

Base unit: `0.25rem` (4px at default root).

| Token | Value | Common use |
|-------|-------|------------|
| `--spacing-xs` | `0.25rem` | Tight inline gap. |
| `--spacing-sm` | `0.5rem` | Form field gap, icon margin. |
| `--spacing-md` | `1rem` | Default block gap. |
| `--spacing-lg` | `1.5rem` | Section internal padding. |
| `--spacing-xl` | `2rem` | Section outer margin. |
| `--spacing-2xl` | `3rem` | Page-level vertical rhythm. |

No `3xl` / `4xl` yet. If a hero or splash view needs larger rhythm, add tokens and document here.

---

## Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-none` | `0` | Sharp corners (default for most Musinsa-style surfaces). |
| `--radius-sm` | `2px` | Micro rounding (chips, tags). |
| `--radius-md` | `4px` | Form inputs, small buttons. |
| `--radius-lg` | `6px` | Cards, panels. |
| `--radius-xl` | `8px` | Modals, larger surfaces. |
| `--radius-round` | `50%` | Circular avatars. |
| `--radius-pill` | `999px` | Pill-shaped status chips. |

Nothing bubbly. `--radius-xl` (8px) is the ceiling for rectangular surfaces.

---

## Shadows

Light:

| Token | Value | Usage |
|-------|-------|-------|
| `--shadow-none` | `none` | Default — flat surfaces. |
| `--shadow-sm` | `0 1px 2px rgba(0, 0, 0, 0.04)` | Subtle lift (hover cards). |
| `--shadow-md` | `0 2px 8px rgba(0, 0, 0, 0.08)` | Card resting state. |
| `--shadow-lg` | `0 4px 16px rgba(0, 0, 0, 0.12)` | Dropdown, popover. |
| `--shadow-modal` | `0 8px 32px rgba(0, 0, 0, 0.16)` | Modal dialog. |

Dark:

| Token | Value |
|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(0, 0, 0, 0.3)` |
| `--shadow-md` | `0 2px 8px rgba(0, 0, 0, 0.4)` |
| `--shadow-lg` | `0 4px 16px rgba(0, 0, 0, 0.5)` |
| `--shadow-modal` | `0 8px 32px rgba(0, 0, 0, 0.6)` |

(`--shadow-none` is not overridden in dark — `none` stays `none`.)

Dark shadows are deeper because the surface and the shadow source both move toward black; without higher alpha the lift disappears.

---

## Transitions

| Token | Value | Usage |
|-------|-------|-------|
| `--transition-fast` | `0.15s ease` | Button press, input focus. |
| `--transition-normal` | `0.2s ease` | Hover, state swap. |
| `--transition-slow` | `0.3s ease` | Modal fade, section reveal. |

No motion tokens for enter/exit, no spring curves, no scroll-driven motion. Keep motion minimal and functional.

---

## Dark Mode Override Rules

**Trigger:** `@media (prefers-color-scheme: dark)` — system preference only. No manual toggle in the current app.

**Declaration location:** One block at the end of `static/css/styles.css` (line 2971–3134). The block re-declares `:root` with dark values, then restates a small set of component-level overrides (header, inputs, buttons, modal overlays, scrollbars, spinner) where component rules in light mode assumed light values directly rather than through a token.

**Rules:**

1. **Every new color token must have a dark counterpart.** When adding `--color-foo` in light, add the dark value in the same PR, in the dark block.
2. **Dark inverts monochrome, does not re-brand.** `--color-black`/`--color-white` swap. The design stays the same system, not a different one.
3. **Role-based message tokens keep their semantic meaning in dark.** Mentor stays blue; student stays neutral. Brightness shifts, relationship doesn't.
4. **Shadows get deeper, not wider.** Same offset/blur, higher alpha.
5. **Component-level dark rules (below the `:root` override) are fallbacks for places the component CSS hard-codes a color instead of using a token.** Long term, those places should be refactored to use tokens so the `:root` override is sufficient. Do not expand the component-level dark block without noting the gap here.

---

## Accessibility Principles

- **Contrast:** Every color pair used for text must pass WCAG AA (≥4.5:1 for body, ≥3.0:1 for large). See the contrast tables above. Tokens that fail are listed with their safe-use caveats.
- **Focus:** `:focus-visible` is a 2px solid `--color-black` outline with 2px offset (`styles.css` lines 142-155). Do not remove outlines. If you need a custom focus style, keep ≥2px and ≥3:1 contrast against the surface.
- **Skip link:** `.skip-link` is present for keyboard-only users (lines 157-173). Preserve it on any layout that adds navigation.
- **Touch targets:** There is no tokenized minimum. Treat 44×44px (per WCAG 2.5.5) as the floor for any interactive element. Add a `--touch-target-min: 44px` token if you need to enforce it in more than one place.
- **Reduced motion:** There is no `prefers-reduced-motion` handling yet. If a future change introduces non-trivial motion (page transitions, parallax, auto-advancing content), add a media query that zeroes `--transition-*` under `prefers-reduced-motion: reduce` and document the gap here.
- **Language:** The UI is Korean-first. Pretendard is the primary face. Do not introduce English-only display fonts without a Korean fallback.

---

## Verification Script

Automated coverage of the token inventory is enforced by a pre-commit hook. The script verifies that every `--*` token declared in `static/css/styles.css` is documented, and — separately — that every token redeclared in the dark-mode override appears under a `Dark:` labelled section of this document. This prevents silent dark-theme drift: adding a dark override in CSS without updating the dark table in `DESIGN.md` fails the hook.

### Location

- Script: [`scripts/verify_design_tokens.py`](scripts/verify_design_tokens.py) — Python 3.11, no extra runtime deps.
- Hook config: [`.pre-commit-config.yaml`](.pre-commit-config.yaml) under `repo: local` → `id: verify-design-tokens`.

### Behavior

1. Splits `static/css/styles.css` at `@media (prefers-color-scheme: dark)`. Collects token sets for the top-level `:root` (light) and the dark-mode `:root` override.
2. **Light check:** every light-declared token must appear somewhere in `DESIGN.md`.
3. **Dark check:** every dark-redeclared token must appear inside a section that begins with a `Dark:` label line and ends at the next `Light:` / `Dark:` label or markdown heading. This enforces that the dark value is actually listed in the dark table, not just mentioned in prose.
4. Emits a per-token `PASS` / `FAIL` report (light tokens first, then dark override tokens). Exit code `0` on full coverage, `1` on any miss.

### When it runs

The hook fires automatically on commits that touch:

- `static/css/styles.css` (new or changed token → must document)
- `DESIGN.md` (token removed → must also remove from CSS or re-add)
- `scripts/verify_design_tokens.py` (script changed → re-verify)

Other commits skip it. GitHub Actions CI is not yet configured in this repo; if a workflow is added later, `python scripts/verify_design_tokens.py` can be dropped into the job verbatim.

### Manual run

```bash
python scripts/verify_design_tokens.py
```

Expected tail on success:

```
All 81 token(s) documented in DESIGN.md.
```

### Failure mode

When a token is missing, stderr lists every missing `--name` and the commit is rejected. Fix by adding the literal token string (inside a table cell or prose line) to `DESIGN.md`.

---

## Decisions Log

| Date | Decision | Rationale | Source |
|------|----------|-----------|--------|
| 2026-04-21 | Initial DESIGN.md created. | Issue #16 — close the gap between CSS tokens and human-readable design intent. | deep-interview spec `dominelinux-main-deep-interview-issue-16-20260421-222116.md` |
| 2026-04-21 | Musinsa-inspired monochrome aesthetic locked in. | Existing aesthetic; avoid scope creep into rebrand. | deep-interview Round 2 |
| 2026-04-21 | WCAG AA contrast computed with real values, not described. | Verifiability over assertion; also exposes two unsafe tokens (`text-tertiary`, `text-muted`) and one borderline pair (warning-text/warning-bg) that previously were implicit. | deep-interview AC #5 |
| 2026-04-21 | Token coverage enforced by script, not review checklist. | 80+ tokens × light+dark makes manual review unreliable. | deep-interview Round 3 |
| 2026-04-21 | Verification script tightened to check light and dark sections separately. | Initial script only checked whether a token name appeared anywhere in DESIGN.md, missing the case where a dark override exists in CSS but the `Dark:` table in DESIGN.md is stale or absent. Script now splits CSS at the `@media` boundary and requires dark-redeclared tokens to appear inside a `Dark:` labelled section. This catch itself exposed that the Shadows section was a combined `Light|Dark` table with no `Dark:` label, which has been split into matching `Light:` / `Dark:` tables for consistency with the color sections. | Codex review finding (P2) on PR #22 |
| 2026-04-19 | Mentor/student message bubble tokens added. | Visual distinction between expert intervention and student voice in the dialogue view. | PR #18 / issue #15 |

---

*End of DESIGN.md.*
