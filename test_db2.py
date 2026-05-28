import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from bot.database import save_user

async def main():
    try:
        res = await save_user(123456, "testuser", "Test", "User", "main")
        print("RESULT:", res)
    except Exception as e:
        print("ERROR:", e)

asyncio.run(main())
