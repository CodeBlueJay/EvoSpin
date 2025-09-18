import os, aiosqlite
from dotenv import load_dotenv

load_dotenv()

DB_URL = "data.db"

async def test_db():
    async with aiosqlite.connect(DB_URL) as db:
        table = await db.execute("""
        SELECT * FROM Users;
        """)
        print(await table.fetchall())

async def init_db():
    async with aiosqlite.connect(DB_URL) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS Users (
            UserID int,
            XP int
        );
        """)
        await db.commit()

async def add_to_inventory():
    async with aiosqlite.connect(DB_URL) as db:
        await db.execute("""
        STATEMENT;
        """)
        await db.commit()