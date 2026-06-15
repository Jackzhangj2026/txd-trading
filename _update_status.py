import asyncio
import sys
sys.path.insert(0, 'E:/hollowsheet')

from backend.database import async_session
from backend.tasks.update_crm_status import update_contacted_status

async def run():
    async with async_session() as db:
        result = await update_contacted_status(db)
        print(result)

asyncio.run(run())
