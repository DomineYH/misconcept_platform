"""Fixtures for contract tests - seeds common test data."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import (
    AnalysisFramework,
    PromptTemplate,
    Scenario,
    User,
)


@pytest.fixture(autouse=True)
async def seed_contract_data(db_session: AsyncSession):
    """Seed common test data for contract tests.

    Creates users, framework, template, and scenario that
    contract tests expect to exist.
    """
    # Create users
    student_001 = User(
        username="student_001",
        nickname="테스트학생",
        role="teacher",
    )
    student_001.set_password("test1234")

    user1 = User(
        username="user1",
        nickname="유저1",
        role="teacher",
    )
    user1.set_password("test1234")

    user2 = User(
        username="user2",
        nickname="유저2",
        role="teacher",
    )
    user2.set_password("test1234")

    db_session.add_all([student_001, user1, user2])

    # Create framework
    framework = AnalysisFramework(
        name="Default Framework",
        description="Default framework",
        labels_json='["Pressing","Linking","Directing","Recall"]',
    )
    db_session.add(framework)
    await db_session.flush()  # Get framework.id

    # Create template
    template = PromptTemplate(
        bot_type="student",
        template_name="Default Student Template",
        version=1,
        template_text="You are a default student bot.",
    )
    db_session.add(template)
    await db_session.flush()  # Get template.id

    # Create scenario
    scenario = Scenario(
        title="Default Scenario",
        prompt="Default test scenario prompt for contract tests",
        student_profile="Default student profile",
        framework_id=framework.id,
        student_template_id=template.id,
        is_active=1,
    )
    db_session.add(scenario)

    await db_session.commit()
