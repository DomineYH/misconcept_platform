"""Schema-ORM integrity validation tests (T101).

기계사제의 축복 아래, 스키마와 ORM의 일치성을 검증하는 성스러운 의식.
이 테스트는 데이터베이스 스키마와 SQLAlchemy ORM 정의가 정확히 일치하는지
자동으로 검증하여 Phase 6 사건과 같은 불일치를 사전에 방지합니다.

검증 항목:
1. ORM에 정의된 모든 컬럼이 데이터베이스에 존재
2. Scenario 모델의 4개 override 컬럼 명시적 검증
3. 컬럼 타입 일치 검증 (String → TEXT, Integer → INTEGER 등)
"""
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.scenario import Scenario


# 옴니시아의 지혜: SQLAlchemy 타입을 SQLite 타입으로 매핑
SQLALCHEMY_TO_SQLITE_TYPE_MAP = {
    "VARCHAR": "TEXT",
    "TEXT": "TEXT",
    "INTEGER": "INTEGER",
    "FLOAT": "REAL",
    "REAL": "REAL",
    "BOOLEAN": "INTEGER",  # SQLite stores boolean as integer
    "DATETIME": "DATETIME",
}


def normalize_sqlite_type(sqlite_type: str) -> str:
    """SQLite 타입 문자열 정규화.

    예: "VARCHAR(200)" → "TEXT", "INTEGER" → "INTEGER"
    """
    # Remove length specifier for VARCHAR/CHAR
    if "(" in sqlite_type:
        base_type = sqlite_type.split("(")[0]
    else:
        base_type = sqlite_type

    return SQLALCHEMY_TO_SQLITE_TYPE_MAP.get(
        base_type.upper(), base_type.upper()
    )


async def get_database_columns(
    session: AsyncSession, table_name: str
) -> dict[str, dict]:
    """데이터베이스에서 실제 컬럼 정보 조회 (PRAGMA table_info).

    Returns:
        dict mapping column_name to {type, notnull, dflt_value, pk}
    """
    result = await session.execute(
        text(f"PRAGMA table_info({table_name})")
    )
    rows = result.fetchall()

    columns = {}
    for row in rows:
        # PRAGMA table_info returns: (cid, name, type, notnull, dflt_value, pk)
        columns[row[1]] = {
            "type": normalize_sqlite_type(row[2]),
            "notnull": bool(row[3]),
            "default": row[4],
            "pk": bool(row[5]),
        }

    return columns


def get_orm_columns(model_class) -> dict[str, dict]:
    """SQLAlchemy ORM 모델에서 컬럼 정보 추출.

    Returns:
        dict mapping column_name to {type, nullable, primary_key}
    """
    inspector = inspect(model_class)
    columns = {}

    for column in inspector.columns:
        # Get the base type name
        type_name = column.type.__class__.__name__.upper()

        # Map SQLAlchemy types to SQLite types
        if type_name in ("STRING", "VARCHAR"):
            sqlite_type = "TEXT"
        elif type_name == "INTEGER":
            sqlite_type = "INTEGER"
        elif type_name == "FLOAT":
            sqlite_type = "REAL"
        elif type_name == "BOOLEAN":
            sqlite_type = "INTEGER"  # SQLite stores boolean as integer
        elif type_name in ("TEXT", "DATETIME"):
            sqlite_type = type_name
        else:
            sqlite_type = type_name

        columns[column.name] = {
            "type": sqlite_type,
            "nullable": column.nullable,
            "primary_key": column.primary_key,
        }

    return columns


@pytest.mark.asyncio
async def test_scenario_schema_matches_orm(
    db_session: AsyncSession,
) -> None:
    """Scenario 모델의 모든 ORM 컬럼이 데이터베이스에 존재하는지 검증.

    Phase 6 사건 재발 방지:
    - ORM에 정의된 컬럼이 데이터베이스에 누락되면 테스트 실패
    - 마이그레이션 후 이 테스트를 실행하여 무결성 보장
    """
    # 1. ORM 컬럼 정보 추출
    orm_columns = get_orm_columns(Scenario)

    # 2. 데이터베이스 컬럼 정보 조회
    db_columns = await get_database_columns(db_session, "scenario")

    # 3. ORM 컬럼이 모두 데이터베이스에 존재하는지 검증
    missing_columns = []
    type_mismatches = []

    for col_name, col_info in orm_columns.items():
        if col_name not in db_columns:
            missing_columns.append(col_name)
        else:
            # Type validation
            expected_type = col_info["type"]
            actual_type = db_columns[col_name]["type"]

            if expected_type != actual_type:
                type_mismatches.append(
                    f"{col_name}: ORM={expected_type}, "
                    f"DB={actual_type}"
                )

    # 4. 검증 결과 단언
    assert not missing_columns, (
        f"ORM에 정의되었으나 데이터베이스에 누락된 컬럼: "
        f"{missing_columns}\n"
        f"옴니시아의 경고: 마이그레이션을 실행하십시오!"
    )

    assert not type_mismatches, (
        f"ORM과 데이터베이스 간 타입 불일치:\n"
        f"{chr(10).join(type_mismatches)}\n"
        f"옴니시아의 경고: 스키마 정의를 수정하십시오!"
    )


@pytest.mark.asyncio
async def test_scenario_override_columns_exist(
    db_session: AsyncSession,
) -> None:
    """Scenario 모델의 4개 override 컬럼 명시적 검증.

    Phase 2에서 추가된 채팅봇 설정 override 컬럼:
    - chat_model (String)
    - chat_temperature (Float)
    - tutor_enabled (Boolean)
    - tutor_intervention_threshold (Integer)

    이 컬럼들이 누락되면 채팅봇 설정이 작동하지 않으므로 명시적 검증.
    """
    # 데이터베이스 컬럼 정보 조회
    db_columns = await get_database_columns(db_session, "scenario")

    # 4개 override 컬럼 존재 검증
    required_override_columns = {
        "chat_model": "TEXT",
        "chat_temperature": "REAL",
        "tutor_enabled": "INTEGER",  # Boolean → INTEGER in SQLite
        "tutor_intervention_threshold": "INTEGER",
    }

    missing = []
    type_errors = []

    for col_name, expected_type in required_override_columns.items():
        if col_name not in db_columns:
            missing.append(col_name)
        elif db_columns[col_name]["type"] != expected_type:
            type_errors.append(
                f"{col_name}: expected {expected_type}, "
                f"got {db_columns[col_name]['type']}"
            )

    assert not missing, (
        f"필수 채팅봇 override 컬럼 누락: {missing}\n"
        f"옴니시아의 경고: Phase 2 마이그레이션을 실행하십시오!"
    )

    assert not type_errors, (
        f"채팅봇 override 컬럼 타입 오류:\n"
        f"{chr(10).join(type_errors)}\n"
        f"옴니시아의 경고: 스키마 타입을 수정하십시오!"
    )


@pytest.mark.asyncio
async def test_all_models_schema_integrity(
    db_session: AsyncSession,
) -> None:
    """전체 모델의 스키마 무결성 검증 (확장 가능).

    현재는 Scenario만 검증하지만, 향후 다른 모델도 추가 가능.
    """
    from src.models import (
        User,
        AnalysisFramework,
        Session as DialogueSession,
        Message,
        QuestionAnalysis,
        SessionSummary,
        ApiUsageLog,
        PromptTemplate,
    )

    models_to_test = [
        (Scenario, "scenario"),
        (User, "user"),
        (AnalysisFramework, "analysis_framework"),
        (DialogueSession, "session"),
        (Message, "message"),
        (QuestionAnalysis, "question_analysis"),
        (SessionSummary, "session_summary"),
        (ApiUsageLog, "api_usage_log"),
        (PromptTemplate, "prompt_template"),
    ]

    all_errors = []

    for model_class, table_name in models_to_test:
        orm_columns = get_orm_columns(model_class)
        db_columns = await get_database_columns(db_session, table_name)

        missing = [
            col for col in orm_columns.keys()
            if col not in db_columns
        ]

        if missing:
            all_errors.append(
                f"{table_name}: 누락된 컬럼 {missing}"
            )

    assert not all_errors, (
        f"스키마-ORM 불일치 발견:\n"
        f"{chr(10).join(all_errors)}\n"
        f"옴니시아의 경고: 모든 마이그레이션을 실행하십시오!"
    )


# 옴니시아의 축복: 이 테스트들이 영원히 불일치를 막아주기를.
# 기계사제의 서명: Schema Integrity Validation v1.0
