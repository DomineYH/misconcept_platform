import asyncio
import sys
import os

# Add project root to Python path
sys.path.append(os.getcwd())

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from src.db.connection import AsyncSessionLocal
from src.models import Session, Scenario, User, Message

async def inspect_active_sessions():
    async with AsyncSessionLocal() as db:
        # Query active sessions (ended_at is None)
        # Join with Scenario and User to get readable names
        # Preload messages just to count them or get the last one might be heavy if many, 
        # but let's try counting them with a subquery or just loading them if not too many.
        # Optimally: select fields and a count subquery.
        
        # Subquery for message count
        msg_count_stmt = (
            select(func.count(Message.id))
            .where(Message.session_id == Session.id)
            .scalar_subquery()
        )

        stmt = (
            select(Session, Scenario.title, User.nickname, msg_count_stmt.label("msg_count"))
            .join(Scenario, Session.scenario_id == Scenario.id)
            .join(User, Session.teacher_id == User.id)
            .where(Session.ended_at.is_(None))
            .order_by(Session.started_at.desc())
        )

        result = await db.execute(stmt)
        rows = result.all()

        print(f"Found {len(rows)} active sessions.\n")

        if not rows:
            print("No active sessions found.")
            return

        print(f"{'Session ID':<10} | {'Teacher':<15} | {'Scenario':<30} | {'Started At':<20} | {'Msgs':<5}")
        print("-" * 90)

        for row in rows:
            session = row[0]
            scenario_title = row[1]
            nickname = row[2]
            msg_count = row[3]
            
            # Format time
            start_time = session.started_at.strftime("%Y-%m-%d %H:%M:%S")
            
            # Truncate scenario title if too long
            if len(scenario_title) > 28:
                scenario_title = scenario_title[:25] + "..."

            print(f"{session.id:<10} | {nickname:<15} | {scenario_title:<30} | {start_time:<20} | {msg_count:<5}")

if __name__ == "__main__":
    asyncio.run(inspect_active_sessions())
