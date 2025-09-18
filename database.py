import os, aiosqlite
from dotenv import load_dotenv

load_dotenv()

DB_URL = "data.db"

inventory = {}

translations = {
    "bb": "Basic Ball",
    "s": "Stickman"
}

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
            XP int,
            Inventory varchar(255)
        );
        """)
        await db.commit()

async def encrypt_inventory(inventory):
    string = ""
    for key, value in inventory.items():
        for k, v in translations.items():
            if key == v:
                string += k
        string += f"[{str(value)}|"
    string = string[:-1]
    return string

async def decrypt_inventory(string):
    strlist = string.split("|")
    strdict = {}
    for i in strlist:
        key = i[:i.index("[")]
        value = int(i[i.index("[")+1:])
        for k, v in translations.items():
            if k == key:
                key = v
        strdict[key] = value
    return strdict


async def add_to_inventory():
    async with aiosqlite.connect(DB_URL) as db:
        await db.execute("""
        STATEMENT;
        """)
        await db.commit()