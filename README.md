# Misconception Dialogue Simulator

A three-party dialogue simulator for teacher training where teachers practice pedagogical questioning with AI-powered student chatbots exhibiting misconceptions, while tutor chatbots provide real-time feedback and intervention.

## 🎯 Project Status

**Implementation Progress**: 99/112 tasks (88.4%) | **Phase 8**: 8/13 tasks (62%)

### Completed Features

- ✅ **Phase 1-2**: Project setup and infrastructure (Complete)
- ✅ **Phase 3**: MVP Dialogue System (Complete)
  - Teacher authentication with session management
  - Scenario selection and dialogue interface
  - AI student bot with misconception role-play (GPT-4-turbo)
  - AI tutor bot with intervention logic (GPT-3.5-turbo)
  - Three-party real-time conversation flow
- ✅ **Phase 4**: Session Analysis (Complete)
  - Post-dialogue question classification
  - Frequency distribution analysis
  - CSV export with anonymization
- ✅ **Phase 5**: Admin Scenario Management (Complete)
  - CRUD operations for dialogue scenarios
  - Role-based access control (admin)
- ✅ **Phase 6**: Framework Configuration (Complete)
  - Custom analysis framework creation
  - Dynamic label configuration (2-20 labels)
- ✅ **Phase 7**: Admin Session Logs (Complete)
  - Session filtering and search
  - Bulk CSV export
  - Aggregated statistics dashboard
- ✅ **Phase 3 (Advanced)**: Dynamic Configuration & Analytics (Complete)
  - API usage tracking with cost analysis
  - Prompt template management with versioning
  - Dynamic prompt loading with caching
- 🚧 **Phase 8**: Production Polish (62% complete)
  - ✅ Error handling with exponential backoff
  - ✅ Rate limiting (slowapi)
  - ✅ SQLite WAL mode
  - ✅ Structured JSON logging
  - ✅ CORS and security headers
  - ✅ Health and metrics endpoints
  - ✅ Code review and refactoring
  - ⏳ Documentation updates (in progress)
  - ⏳ Pre-commit hooks
  - ⏳ Performance optimization
  - ⏳ Security hardening

See `specs/001-misconception-dialogue-sim/STATUS.md` for detailed status.

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- OpenAI API key (GPT-4 and GPT-3.5 access)
- 2GB RAM minimum, 4GB recommended

### Installation

```bash
# 1. Clone repository
git clone https://github.com/your-org/misconcept_platform.git
cd misconcept_platform

# 2. Create virtual environment with uv
uv venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. Install dependencies
uv pip install -e ".[dev]"

# 4. Configure environment
cp .env.example .env

# Edit .env and configure:
# - OPENAI_API_KEY=sk-your-key-here
# - SESSION_SECRET=your-secure-secret-key
# - Other settings as needed

# 5. Initialize database
python -m src.db.seed

# This creates:
# - Default analysis framework ("High/Low Leverage")
# - Admin user (student_uid: admin_001, nickname: 관리자)
# - Sample scenario

# 6. Run development server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Visit http://localhost:8000

### First Login

- **Login URL**: http://localhost:8000/login
- **Teacher Login**: Use any student_uid + nickname (creates new user)
- **Admin Login**: student_uid=`admin_001`, nickname=`관리자`

## 📚 Core Features

### 🎓 Teacher Experience

1. **Login**: Simple authentication with student ID and nickname
2. **Scenario Selection**: Browse and select active dialogue scenarios
3. **Three-Party Dialogue**:
   - Teacher asks questions to student bot
   - Student bot responds maintaining misconception
   - Tutor bot provides pedagogical feedback
   - Real-time interventions when needed
4. **Session Analysis**:
   - Question classification by analysis framework
   - Frequency distribution visualization
   - CSV export for research

### 👨‍💼 Admin Features

1. **Dashboard**: Aggregate statistics and session overview
2. **Scenario Management**:
   - Create, edit, and activate/deactivate scenarios
   - Configure misconception profiles
   - Associate with analysis frameworks
3. **Framework Configuration**:
   - Define custom question classification systems
   - Configure 2-20 labels per framework
   - Apply to scenarios
4. **Session Logs**:
   - Filter sessions by date range and teacher
   - View detailed session transcripts
   - Bulk CSV export for research
   - Statistics dashboard
5. **API Usage Analytics** (Phase 3):
   - Real-time API usage tracking with token counts
   - Cost analysis by model, scenario, and bot type
   - Date range filtering and CSV export
   - Accurate cost calculation for gpt-4o, gpt-4o-mini, etc.
6. **Prompt Template Management** (Phase 3):
   - Create and manage system prompts via web UI
   - Version control with automatic versioning
   - Dynamic prompt loading with 5-minute TTL caching
   - Fallback mechanism: Cache → DB → File System → Hardcoded

## 🏗️ Technology Stack

### Backend
- **Framework**: FastAPI (async web framework)
- **Database**: SQLite3 with SQLAlchemy 2.x (async ORM)
- **LLM**: OpenAI API (GPT-4-turbo, GPT-3.5-turbo)
- **Authentication**: Session-based with secure cookies
- **Rate Limiting**: slowapi (IP-based)
- **Logging**: python-json-logger (structured logs)

### Frontend
- **Templates**: Jinja2 (server-side rendering)
- **Interactivity**: HTMX (partial updates, polling)
- **Styling**: CSS (lightweight, responsive)

### Production
- **Server**: uvicorn with multiple workers
- **Reverse Proxy**: nginx
- **SSL**: Let's Encrypt
- **Monitoring**: Health and metrics endpoints

## 📁 Project Structure

```
misconcept_platform/
├── src/
│   ├── models/              # SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── scenario.py
│   │   ├── session.py
│   │   ├── message.py
│   │   ├── analysis_framework.py
│   │   ├── question_analysis.py
│   │   ├── session_summary.py
│   │   ├── chatbot_config.py      # Phase 3: Bot configuration
│   │   └── prompt_template.py     # Phase 3: Prompt versioning
│   ├── services/            # Business logic
│   │   ├── student_bot.py   # AI student with misconception
│   │   ├── tutor_bot.py     # AI tutor with interventions
│   │   ├── analyzer.py      # Question classification
│   │   ├── session_mgr.py   # Dialogue orchestration
│   │   ├── export.py        # CSV export with anonymization
│   │   ├── config_cache.py  # Phase 3: Bot config caching
│   │   └── prompt_manager.py # Phase 3: Dynamic prompt loading
│   ├── api/
│   │   ├── routes/          # FastAPI endpoints
│   │   │   ├── auth.py      # Login/logout
│   │   │   ├── scenarios.py # Scenario selection
│   │   │   ├── sessions.py  # Dialogue and analysis
│   │   │   ├── admin.py     # Admin dashboard
│   │   │   ├── admin_scenarios.py    # Scenario CRUD
│   │   │   ├── admin_frameworks.py   # Framework CRUD
│   │   │   ├── admin_sessions.py     # Session logs
│   │   │   ├── admin_chatbot_config.py # Phase 3: Config UI
│   │   │   └── health.py    # Health/metrics
│   │   ├── dependencies.py  # Dependency injection
│   │   └── schemas.py       # Pydantic models
│   ├── templates/           # Jinja2 HTML templates
│   │   ├── login.html
│   │   ├── scenarios.html
│   │   ├── chat.html
│   │   ├── analysis.html
│   │   └── admin/           # Admin UI
│   ├── prompts/             # LLM system prompts
│   │   ├── student_system.txt
│   │   ├── tutor_system.txt
│   │   └── analysis_prompt.txt
│   ├── db/                  # Database utilities
│   │   ├── connection.py    # Async engine & session
│   │   └── seed.py          # Initial data
│   ├── config.py            # Environment configuration
│   └── main.py              # FastAPI application
├── tests/
│   ├── contract/            # API contract tests
│   ├── integration/         # End-to-end tests
│   └── unit/                # Service/model tests
├── static/                  # Static assets
│   ├── css/
│   └── js/
├── docs/                    # Documentation
│   ├── deployment.md        # Production deployment guide
│   ├── security.md          # Security hardening guide
│   ├── admin_chatbot_config_guide.md  # Admin chatbot config UI guide
│   ├── developer_chatbot_config_guide.md  # Developer config guide
│   └── spec.md              # Feature specification
├── specs/                   # Implementation specs
│   └── 001-misconception-dialogue-sim/
│       ├── STATUS.md        # Current status
│       ├── spec.md          # Feature spec
│       ├── plan.md          # Implementation plan
│       └── tasks.md         # Task breakdown
└── pyproject.toml           # Project metadata
```

## 🧪 Testing

### Run All Tests
```bash
pytest
```

### Run Specific Test Suites
```bash
# Contract tests (API endpoints)
pytest tests/contract/

# Integration tests (end-to-end flows)
pytest tests/integration/

# Unit tests (services and models)
pytest tests/unit/
```

### Run with Coverage
```bash
pytest --cov=src --cov-report=html
# View report: open htmlcov/index.html
```

### Known Test Issues
- Admin endpoint tests have isolation issues when run together
- Individual test classes pass successfully
- Run test classes individually for CI/CD:
  ```bash
  pytest tests/contract/test_admin_endpoints.py::TestAdminDashboard
  pytest tests/contract/test_admin_endpoints.py::TestScenarioCreation
  # etc.
  ```

## 🌐 API Endpoints

### Public Endpoints
- `GET /` - Home page (redirects to /login)
- `GET /login` - Login page
- `POST /login` - Authenticate user
- `POST /logout` - End session
- `GET /health` - Health check
- `GET /metrics` - Application metrics

### Teacher Endpoints (requires authentication)
- `GET /scenarios` - List active scenarios
- `GET /scenarios/{id}` - Start dialogue session
- `POST /sessions` - Create new session
- `POST /sessions/{id}/messages` - Send message
- `GET /sessions/{id}/messages/updates` - Poll for new messages (HTMX)
  - Query param: `since` (optional, last message ID)
  - Returns: 200 OK with HTML partial (new messages) or 204 No Content
- `POST /sessions/{id}/end` - End session
- `GET /sessions/{id}/analysis` - View analysis
- `GET /sessions/{id}/export.csv` - Download CSV

### Admin Endpoints (requires admin role)
- `GET /admin` - Admin dashboard
- `GET /admin/scenarios` - Manage scenarios
- `POST /admin/scenarios` - Create scenario
- `PUT /admin/scenarios/{id}` - Update scenario
- `GET /admin/frameworks` - List frameworks
- `POST /admin/frameworks` - Create framework
- `GET /admin/sessions` - Session logs
- `GET /admin/sessions/export` - Bulk CSV export
- `GET /admin/stats` - Statistics
- `GET /admin/chatbot-config` - Bot configuration UI (Phase 3)
- `PUT /admin/chatbot-config` - Update bot settings (Phase 3)
- `GET /admin/chatbot-config/costs` - Cost metrics (Phase 3)
- `GET /admin/api-usage-page` - API usage analytics (Phase 3)
- `GET /admin/prompts-page` - Prompt template management (Phase 3)
- `POST /admin/prompts` - Create prompt template (Phase 3)
- `PUT /admin/prompts/{id}/activate` - Activate prompt (Phase 3)

## 🚀 Production Deployment

See [docs/deployment.md](docs/deployment.md) for detailed production deployment guide.

### Quick Production Setup
```bash
# 1. Configure systemd service
sudo cp deployment/misconcept.service /etc/systemd/system/
sudo systemctl enable misconcept
sudo systemctl start misconcept

# 2. Configure nginx
sudo cp deployment/nginx.conf /etc/nginx/sites-available/misconcept
sudo ln -s /etc/nginx/sites-available/misconcept \
    /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# 3. Set up SSL
sudo certbot --nginx -d your-domain.com

# 4. Configure backups
sudo cp deployment/backup.sh /opt/misconcept_platform/scripts/
sudo chmod +x /opt/misconcept_platform/scripts/backup.sh
sudo crontab -e  # Add: 0 2 * * * /opt/.../backup.sh
```

## 🔧 Development

### Code Style
- **Formatter**: Black (line length: 80)
- **Linter**: Ruff (E, F, I, N, W rules)
- **Type Hints**: Required for public APIs
- **File Length**: Maximum 300 lines (per project constitution)
- **Line Length**: Maximum 80 characters (per project constitution)

### Format and Lint
```bash
# Format code
black .

# Lint code
ruff check .

# Auto-fix issues
ruff check --fix .
```

### Database Migrations
```bash
# Current approach: Manual schema updates
# TODO: Add Alembic for automated migrations
```

### Adding New Features
1. Create feature spec in `specs/`
2. Write tests first (TDD workflow)
3. Implement feature
4. Run tests and ensure they pass
5. Update documentation

## 📝 Documentation

- **Feature Spec**: `specs/001-misconception-dialogue-sim/spec.md`
- **Implementation Plan**: `specs/001-misconception-dialogue-sim/plan.md`
- **Task Breakdown**: `specs/001-misconception-dialogue-sim/tasks.md`
- **Status**: `specs/001-misconception-dialogue-sim/STATUS.md`
- **Deployment**: `docs/deployment.md`
- **API Reference**: See API Endpoints section above

## 🤝 Contributing

### Guidelines
1. Follow TDD workflow (tests first)
2. Adhere to code style (Black + Ruff)
3. Keep files under 300 lines
4. Keep lines under 80 characters
5. Add type hints
6. Update tests and documentation
7. Run full test suite before submitting

### Git Workflow
```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Make changes and commit
git add .
git commit -m "feat: Add your feature description"

# Push and create pull request
git push origin feature/your-feature-name
```

## 📊 Performance

### Current Metrics
- **Response Time**: <200ms for API calls
- **Database**: SQLite with WAL mode for concurrency
- **Rate Limiting**: 5 logins/min, 30 messages/min
- **Workers**: 4 uvicorn workers recommended (2-core)

### Optimization Tips
- Use `--workers` based on CPU cores: `(2 x cores) + 1`
- Enable SQLite WAL mode (already configured)
- Configure nginx caching for static assets
- Monitor with `/metrics` endpoint

## 🔐 Security

### Current Measures
- Session-based authentication with secure cookies
- Rate limiting (slowapi)
- CORS configuration
- Security headers (X-Frame-Options, CSP, HSTS)
- Input validation (Pydantic)
- SQL injection prevention (SQLAlchemy ORM)

### Security Best Practices
- Use strong `SESSION_SECRET` (32+ random bytes)
- Enable HTTPS in production (Let's Encrypt)
- Restrict database file permissions (640)
- Regular dependency updates
- Monitor logs for suspicious activity

## 📈 Monitoring

### Health Check
```bash
curl https://your-domain.com/health
```

Response:
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2025-01-06T12:00:00Z"
}
```

### Metrics
```bash
curl https://your-domain.com/metrics
```

Response:
```json
{
  "total_users": 150,
  "total_sessions": 450,
  "total_messages": 12500,
  "uptime_seconds": 86400,
  "database_size_mb": 12.5
}
```

## 📄 License

This project is licensed under the MIT License.

## 🙏 Acknowledgments

- OpenAI for GPT-4 and GPT-3.5 APIs
- FastAPI for the excellent async web framework
- HTMX for seamless partial updates
- SQLAlchemy for robust ORM
- All contributors and testers

## 📞 Support

- **GitHub Issues**: [Create an issue](https://github.com/your-org/misconcept_platform/issues)
- **Documentation**: See `docs/` directory
- **Status**: `specs/001-misconception-dialogue-sim/STATUS.md`

---

**Version**: 0.8.8 | **Status**: Production-Ready (Phase 8 in progress) | **Last Updated**: 2025-01-06
