"""Shared fixtures for integration tests."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.user_group import UserGroup
from src.models.analysis_framework import AnalysisFramework
from src.models.scenario import Scenario
from src.models.scenario_group import ScenarioGroup
from src.models.prompt_template import PromptTemplate


@pytest.fixture
async def test_group(db_session: AsyncSession) -> UserGroup:
    """Create a test user group."""
    group = UserGroup(
        name="Integration Test Group",
        description="Group for integration tests",
    )
    db_session.add(group)
    await db_session.commit()
    await db_session.refresh(group)
    return group


@pytest.fixture
async def admin_user(
    db_session: AsyncSession, test_group: UserGroup
) -> User:
    """Create an admin user for testing."""
    user = User(
        username="admin_001",
        nickname="관리자",
        role="admin",
        group_id=test_group.id,
    )
    user.set_password("test1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def teacher_user(
    db_session: AsyncSession, test_group: UserGroup
) -> User:
    """Create a teacher user for testing."""
    user = User(
        username="teacher_001",
        nickname="김교사",
        role="teacher",
        group_id=test_group.id,
    )
    user.set_password("test1234")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_framework(db_session: AsyncSession) -> AnalysisFramework:
    """Create test analysis framework."""
    framework = AnalysisFramework(
        name="Test Framework",
        description="Framework for testing",
        labels_json='["high_leverage", "medium_leverage", "low_leverage"]',
    )
    db_session.add(framework)
    await db_session.commit()
    await db_session.refresh(framework)
    return framework


@pytest.fixture
async def original_framework(
    db_session: AsyncSession,
) -> AnalysisFramework:
    """Create the original framework (alias for framework switching tests)."""
    framework = AnalysisFramework(
        name="Original Framework",
        description="Original framework for testing",
        labels_json='["Pressing", "Linking", "Directing", "Recall"]',
    )
    db_session.add(framework)
    await db_session.commit()
    await db_session.refresh(framework)
    return framework


@pytest.fixture
async def test_student_template(db_session: AsyncSession) -> PromptTemplate:
    """Create test student template."""
    template = PromptTemplate(
        bot_type="student",
        template_name="Test Student Template",
        version=1,
        template_text=(
            "You are a test student bot. Scenario: {scenario_title}. "
            "Profile: {student_profile}. Context: {prompt}"
        ),
    )
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)
    return template


@pytest.fixture
async def test_tutor_template(db_session: AsyncSession) -> PromptTemplate:
    """Create test tutor template."""
    template = PromptTemplate(
        bot_type="tutor",
        template_name="Test Tutor Template",
        version=1,
        template_text=(
            "You are a test tutor bot. Scenario: {scenario_title}. "
            "Profile: {student_profile}. Context: {prompt}"
        ),
    )
    db_session.add(template)
    await db_session.commit()
    await db_session.refresh(template)
    return template


@pytest.fixture
async def test_scenario(
    db_session: AsyncSession,
    test_framework: AnalysisFramework,
    test_student_template: PromptTemplate,
    test_group: UserGroup,
) -> Scenario:
    """Create test scenario with student template and group access."""
    scenario = Scenario(
        title="Test Scenario",
        prompt="Test prompt for scenario",
        student_profile="Test student profile",
        framework_id=test_framework.id,
        student_template_id=test_student_template.id,
        is_active=1,
    )
    db_session.add(scenario)
    await db_session.flush()  # Get scenario.id

    # Link scenario to group
    scenario_group = ScenarioGroup(
        scenario_id=scenario.id,
        group_id=test_group.id,
    )
    db_session.add(scenario_group)
    await db_session.commit()
    await db_session.refresh(scenario)
    return scenario


@pytest.fixture
async def test_scenario_with_tutor(
    db_session: AsyncSession,
    test_framework: AnalysisFramework,
    test_student_template: PromptTemplate,
    test_tutor_template: PromptTemplate,
    test_group: UserGroup,
) -> Scenario:
    """Create test scenario with tutor enabled and group access."""
    scenario = Scenario(
        title="Test Scenario with Tutor",
        prompt="Test prompt for tutor intervention testing",
        student_profile="Test student profile",
        framework_id=test_framework.id,
        student_template_id=test_student_template.id,
        tutor_template_id=test_tutor_template.id,
        is_active=1,
    )
    db_session.add(scenario)
    await db_session.flush()  # Get scenario.id

    # Link scenario to group
    scenario_group = ScenarioGroup(
        scenario_id=scenario.id,
        group_id=test_group.id,
    )
    db_session.add(scenario_group)
    await db_session.commit()
    await db_session.refresh(scenario)
    return scenario
