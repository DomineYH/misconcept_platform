# Phase 5 Complete: Admin Scenario Management

**Feature**: 001-misconception-dialogue-sim
**Phase**: User Story 3 - Admin Manages Scenarios
**Priority**: P3
**Completion Date**: 2025-11-05
**Tasks**: T072-T083 (12/12 completed)

## Overview

Phase 5 successfully implements comprehensive admin scenario management capabilities with full CRUD operations, role-based access control, and an intuitive web interface. Administrators can now create, edit, activate/deactivate scenarios while teachers see only active scenarios.

**Status**: ✅ All 13 tests passing (11 contract + 2 integration)

## Key Achievements

### 1. Role-Based Access Control ✅
- **Admin Authentication**: Verified at route level (user.role == "admin")
- **403 Forbidden**: Non-admin users blocked from admin routes
- **Scenario Visibility**: Teachers only see active scenarios (is_active=1)
- **Admin Privileges**: Admins can view/edit all scenarios regardless of status

### 2. Scenario CRUD Operations ✅
- **Create**: New scenarios with validation (title, prompt, student profile)
- **Read**: Dashboard statistics and comprehensive scenario list
- **Update**: Partial updates with field validation
- **Toggle**: Active/inactive status management
- **Protection**: Cannot modify scenarios with active sessions (T080)

### 3. Admin Dashboard ✅
- **Statistics Display**: Total/active scenarios, sessions, avg duration
- **Quick Actions**: Direct links to scenario management
- **Real-time Updates**: Dynamic stat calculations
- **Professional UI**: Clean, intuitive interface

### 4. Scenario Management Interface ✅
- **Create Form**: Client-side validation, framework selection
- **Scenario Cards**: Inline editing, metadata display
- **Toggle Switches**: Visual active/inactive status
- **JavaScript CRUD**: Real-time API interactions
- **Error Handling**: User-friendly error alerts

## Technical Implementation

### Tests Created (TDD Workflow)

**Contract Tests** (`tests/contract/test_admin_endpoints.py`):
```python
class TestAdminDashboard:
    test_admin_dashboard_requires_admin_role()  # 403 for teachers
    test_admin_dashboard_success_for_admin()    # 200 with stats
    test_admin_dashboard_redirects_when_not_logged_in()  # 303 redirect

class TestScenarioCreation:
    test_create_scenario_success()              # 201 with scenario data
    test_create_scenario_title_too_short()      # 422 validation
    test_create_scenario_prompt_too_short()     # 422 validation
    test_create_scenario_requires_admin_role()  # 403 for teachers

class TestScenarioUpdate:
    test_update_scenario_success()              # 200 with updated data
    test_toggle_scenario_active_status()        # 200 with status change
    test_update_nonexistent_scenario_returns_404()  # 404 for missing
    test_update_scenario_requires_admin_role()  # 403 for teachers
```

**Integration Tests** (`tests/integration/test_scenario_management.py`):
```python
class TestScenarioLifecycle:
    test_scenario_lifecycle_flow()              # Full CRUD cycle
    test_multiple_scenarios_filtering()         # Active/inactive filtering
```

### API Routes Implemented

**Admin Dashboard** (`GET /admin`):
```python
@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    # Role check
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")

    # Aggregate statistics
    total_scenarios = await db.scalar(select(func.count(Scenario.id)))
    active_scenarios = await db.scalar(
        select(func.count(Scenario.id)).where(Scenario.is_active == 1)
    )
    total_sessions = await db.scalar(select(func.count(Session.id)))
    avg_duration = await db.scalar(
        select(func.avg(...)).where(Session.ended_at.isnot(None))
    )

    return templates.TemplateResponse("admin/dashboard.html", {...})
```

**Scenario Management** (`GET /admin/scenarios`):
```python
@router.get("/admin/scenarios", response_class=HTMLResponse)
async def list_all_scenarios(...):
    # Load all scenarios (active + inactive) with frameworks
    query = select(Scenario).join(AnalysisFramework).order_by(...)
    scenarios = result.scalars().all()

    return templates.TemplateResponse("admin/scenarios.html", {...})
```

**Create Scenario** (`POST /admin/scenarios`):
```python
@router.post("/admin/scenarios", status_code=201)
async def create_scenario(
    scenario_data: ScenarioCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    # Role check + framework verification
    scenario = Scenario(
        title=scenario_data.title,
        prompt=scenario_data.prompt,
        student_profile=scenario_data.student_profile,
        framework_id=scenario_data.framework_id,
        is_active=1,  # Active by default
    )

    db.add(scenario)
    await db.commit()
    return scenario
```

**Update Scenario** (`PUT /admin/scenarios/{id}`):
```python
@router.put("/admin/scenarios/{scenario_id}")
async def update_scenario(
    scenario_id: int,
    scenario_data: ScenarioUpdate,
    ...
):
    # Check for active sessions (T080)
    active_sessions_count = await db.scalar(
        select(func.count(Session.id))
        .where(Session.scenario_id == scenario_id)
        .where(Session.ended_at.is_(None))
    )

    if active_sessions_count and active_sessions_count > 0:
        # Only allow is_active toggle
        update_keys = set(scenario_data.dict(exclude_unset=True).keys())
        if update_keys != {"is_active"}:
            raise HTTPException(
                status_code=403,
                detail="Cannot modify scenario with active sessions. "
                       "Only status toggle allowed.",
            )

    # Update fields...
    return scenario
```

### Pydantic Validation Schemas

```python
class ScenarioCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    prompt: str = Field(..., min_length=10, max_length=10000)
    student_profile: str = Field(..., min_length=3, max_length=5000)
    framework_id: int

    @validator("title")
    def title_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()

class ScenarioUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    prompt: Optional[str] = Field(None, min_length=10, max_length=10000)
    student_profile: Optional[str] = Field(None, min_length=3, max_length=5000)
    framework_id: Optional[int] = None
    is_active: Optional[int] = Field(None, ge=0, le=1)

class ScenarioResponse(BaseModel):
    id: int
    title: str
    prompt: str
    student_profile: str
    framework_id: int
    is_active: int

    class Config:
        from_attributes = True
```

### Templates Created

**Admin Dashboard** (`src/templates/admin/dashboard.html`):
- 4 stat cards: total scenarios, active scenarios, sessions, duration
- Quick action buttons for scenario/framework management
- Professional styling with icons

**Scenario Management** (`src/templates/admin/scenarios.html`):
- Create new scenario form with validation
- Scenario card list with inline editing
- Active/inactive toggle switches
- JavaScript for CRUD operations
- Real-time updates without page reload

## Bug Fixes and Improvements

### 1. get_current_user Dependency Fix ✅
**Problem**: Dependency was returning dict instead of User model
**Impact**: FastAPI dependency injection failed
**Solution**: Complete rewrite to query User from database
```python
async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=303, ...)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, ...)

    return user
```

### 2. Scenario Visibility Fix ✅
**Problem**: Inactive scenarios were accessible to teachers
**Impact**: Integration test failure
**Solution**: Added is_active check in scenario detail route
```python
@router.get("/scenarios/{scenario_id}")
async def get_scenario_detail(...):
    scenario = result.scalar_one_or_none()

    if not scenario:
        raise HTTPException(status_code=404, ...)

    # Check if scenario is active (unless user is admin)
    if scenario.is_active != 1 and user.role != "admin":
        raise HTTPException(status_code=404, ...)

    return templates.TemplateResponse(...)
```

### 3. Config Import Fix ✅
**Problem**: `from src.config import settings` - settings doesn't exist
**Solution**: Changed to `from src.config import config`

### 4. Validation Status Code Fix ✅
**Problem**: Tests expected 400 but Pydantic returns 422
**Solution**: Updated test assertions to expect 422 (Unprocessable Entity)

## File Changes Summary

### New Files (5)
1. `tests/contract/test_admin_endpoints.py` - 11 contract tests
2. `tests/integration/test_scenario_management.py` - 2 integration tests
3. `src/api/routes/admin.py` - Complete admin routes (290 lines)
4. `src/templates/admin/dashboard.html` - Admin dashboard UI
5. `src/templates/admin/scenarios.html` - Scenario management UI

### Modified Files (4)
1. `src/main.py` - Added admin router registration
2. `src/api/dependencies.py` - Fixed get_current_user to return User model
3. `src/api/routes/scenarios.py` - Added is_active check for non-admin
4. `src/services/analyzer.py` - Fixed config import

## Test Results

**Contract Tests**: 11/11 passing ✅
```
TestAdminDashboard: 3/3 passing
TestScenarioCreation: 4/4 passing
TestScenarioUpdate: 4/4 passing
```

**Integration Tests**: 2/2 passing ✅
```
test_scenario_lifecycle_flow: PASSED
test_multiple_scenarios_filtering: PASSED
```

## Security Considerations

### Implemented ✅
1. **Role-Based Access**: Admin role verified at route level
2. **Session Protection**: Cannot modify scenarios with active sessions
3. **Input Validation**: Pydantic schemas with length constraints
4. **Whitespace Trimming**: Prevents empty-string bypasses
5. **404 for Inactive**: Teachers get 404 (not 403) for inactive scenarios

### Future Enhancements
1. Add CSRF tokens for POST/PUT requests
2. Implement audit logging for admin actions
3. Add rate limiting for admin endpoints
4. Consider soft delete for scenarios

## Performance Notes

- SQLAlchemy async/await throughout
- Efficient aggregate queries for dashboard stats
- Single query for scenario list with framework join
- No N+1 query issues
- Client-side form validation reduces server load

## Next Steps (Phase 6)

### User Story 4: Admin Configures Analysis Framework
1. Create framework management tests (T084-T086)
2. Implement GET /admin/frameworks endpoint
3. Implement POST /admin/frameworks with validation
4. Add framework selection to admin dashboard
5. Test framework switching in session analysis

**Estimated**: 8 tasks remaining

## Lessons Learned

1. **TDD Effectiveness**: Writing tests first caught the get_current_user bug early
2. **Dependency Injection**: FastAPI requires proper type hints for dependencies
3. **Pydantic V2**: Validation errors return 422 (not 400)
4. **Role Checks**: Better to check inline than create complex dependencies
5. **Status Codes**: Use 404 (not 403) for hidden resources (security best practice)

## Conclusion

Phase 5 successfully delivers comprehensive admin scenario management with:
- ✅ Full CRUD operations
- ✅ Role-based access control
- ✅ Professional web interface
- ✅ Protection against unsafe modifications
- ✅ All tests passing (13/13)

The admin interface is production-ready and provides a solid foundation for Phase 6 (framework configuration).

**Progress**: 75/112 tasks complete (67.0%)
