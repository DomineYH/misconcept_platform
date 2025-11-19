import asyncio
import sys
import os
from datetime import datetime, timezone

# Add project root to Python path
sys.path.append(os.getcwd())

from sqlalchemy import select
from src.db.connection import AsyncSessionLocal
from src.models import Scenario

async def delete_all_scenarios():
    async with AsyncSessionLocal() as db:
        # Find all scenarios that are not already deleted
        stmt = select(Scenario).where(Scenario.deleted_at.is_(None))
        result = await db.execute(stmt)
        scenarios = result.scalars().all()
        
        count = len(scenarios)
        if count == 0:
            print("No active scenarios found to delete.")
            return

        print(f"Found {count} scenarios. Soft-deleting them...")

        for scenario in scenarios:
            # Use the model's soft delete logic
            scenario.deleted_at = datetime.now(timezone.utc)
            # Optionally set is_active to 0 as well to be sure
            scenario.is_active = 0
        
        await db.commit()
        print(f"Successfully soft-deleted {count} scenarios.")

if __name__ == "__main__":
    asyncio.run(delete_all_scenarios())
