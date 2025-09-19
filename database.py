import os, aiosqlite
from dotenv import load_dotenv

load_dotenv()

DB_URL = "data.db"

translations = {
    "bb": "Basic Ball",
    "s": "Stickman",
    "d": "Dog"
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
        try:
            key = i[:i.index("[")]
            value = i[i.index("[")+1:]
            for k, v in translations.items():
                if k == key:
                    key = v
            strdict[key] = value if key != "" else ""
            key, value = strdict.popitem()
            if not((key, value) == ('', '')):
                strdict[key] = value
        except:
            strdict = {}
    return strdict

async def get_inventory(user_id):
    await check_user_exist(user_id)
    async with aiosqlite.connect(DB_URL) as db:
        cursor = await db.execute(f"""
        SELECT Inventory FROM Users WHERE UserID = {user_id};
        """)
        inven = await cursor.fetchone()
        if inven[0] == None:
            return ""
        return inven[0]

async def check_user_exist(user_id):
    async with aiosqlite.connect(DB_URL) as db:
        cursor = await db.execute(f"""
        SELECT UserID FROM Users;
        """)
        users_list = await cursor.fetchall()
    if not((user_id,) in users_list):
        await add_user(user_id)

async def add_user(user_id):
    async with aiosqlite.connect(DB_URL) as db:
        await db.execute(f"""
        INSERT INTO Users (UserID, XP, Inventory)
        VALUES ({user_id}, 0, '');
        """)
        await db.commit()

async def add_to_inventory(item, user_id):
    await check_user_exist(user_id)
    inventory = await decrypt_inventory(await get_inventory(user_id))
    try:
        inventory[item] = int(inventory[item])
        inventory[item] += 1
    except:
        inventory[item] = 1
    encrypted = await encrypt_inventory(inventory)
    async with aiosqlite.connect(DB_URL) as db:
        await db.execute(f"""
        UPDATE Users
        SET Inventory = '{encrypted}'
        WHERE UserID = {user_id};
        """)
        await db.commit()