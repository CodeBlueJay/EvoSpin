import os, aiosqlite
from dotenv import load_dotenv

load_dotenv()

DB_URL = "data.db"

async def init_db():
    async with aiosqlite.connect(DB_URL) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY)
        """)
        await db.commit()