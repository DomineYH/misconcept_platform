"""Database migration runner script."""

import asyncio
import os
from pathlib import Path
from sqlalchemy import text

from src.db.connection import engine


async def run_migration(migration_file: Path):
    """Execute a single migration SQL file.

    Args:
        migration_file: Path to SQL migration file
    """
    print(f"Running migration: {migration_file.name}")

    # Read SQL file
    with open(migration_file, 'r', encoding='utf-8') as f:
        migration_sql = f.read()

    # Execute migration
    async with engine.begin() as conn:
        # Split SQL by semicolon and execute each statement
        statements = [
            stmt.strip()
            for stmt in migration_sql.split(";")
            if stmt.strip() and not stmt.strip().startswith("--")
        ]

        for i, stmt in enumerate(statements, 1):
            try:
                # Skip empty or comment-only statements
                if not stmt or all(line.strip().startswith("--") or not line.strip()
                                  for line in stmt.split("\n")):
                    continue

                await conn.execute(text(stmt))
                print(f"  Statement {i}/{len(statements)} executed")
            except Exception as e:
                print(f"Error executing statement {i}:")
                print(f"  SQL: {stmt[:100]}...")
                print(f"  Error: {e}")
                raise

    print(f"✓ Migration {migration_file.name} completed successfully")


async def run_all_migrations():
    """Run all migration files in order."""
    migrations_dir = Path(__file__).parent

    # Get all .sql files sorted by name (001_, 002_, etc.)
    migration_files = sorted(migrations_dir.glob("*.sql"))

    if not migration_files:
        print("No migration files found")
        return

    print(f"Found {len(migration_files)} migration(s) to run")

    for migration_file in migration_files:
        await run_migration(migration_file)

    print("\n✓ All migrations completed successfully")


if __name__ == "__main__":
    asyncio.run(run_all_migrations())
