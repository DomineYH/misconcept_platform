# Misconception Dialogue Simulator

A three-party dialogue simulator for teacher training where teachers practice pedagogical questioning with AI-powered student chatbots exhibiting misconceptions, while tutor chatbots provide real-time feedback.

## 🎯 Project Status

**Implementation Progress**: 15/112 tasks (13.4%)

- ✅ **Phase 1**: Project setup and configuration (Complete)
- ✅ **Phase 2**: Core infrastructure (Complete)  
- 🚧 **Phase 3**: MVP Dialogue System (In Progress)

See `specs/001-misconception-dialogue-sim/progress.md` for detailed progress.

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- OpenAI API key

### Installation

```bash
# 1. Create virtual environment
uv venv
source .venv/bin/activate  # Linux/Mac

# 2. Install dependencies
uv pip install -e ".[dev]"

# 3. Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# 4. Initialize database
python -m src.db.seed

# 5. Run application
uvicorn src.main:app --reload --port 8000
```

Visit http://localhost:8000

## 📚 Technology Stack

- **Backend**: FastAPI (async web framework)
- **Database**: SQLite3 with SQLAlchemy 2.x (async ORM)
- **Templates**: Jinja2 (server-side rendering)
- **Frontend**: HTMX (partial updates)
- **LLM**: OpenAI GPT-4 (dialogue) + GPT-3.5 (analysis)

## 📖 Documentation

- Feature Specification: `specs/001-misconception-dialogue-sim/spec.md`
- Implementation Plan: `specs/001-misconception-dialogue-sim/plan.md`
- Task Breakdown: `specs/001-misconception-dialogue-sim/tasks.md`
- Progress Tracking: `specs/001-misconception-dialogue-sim/progress.md`

---

**Version**: 0.1.0 | **Status**: Foundation Complete
