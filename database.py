import os, aiosqlite, discord, json
from discord.ext import commands
from dotenv import load_dotenv

with open("configuration/items.json", "r") as items:
    things = json.load(items)
with open("configuration/shop.json", "r") as settings:
    potions = json.load(settings)
with open("configuration/crafting.json", "r") as craftables:
    craftables = json.load(craftables)

load_dotenv()

DB_URL = "data.db"

translations = {things[i]["abbev"]: i for i in things}
translations.update({potions[i]["abbev"]: i for i in potions})
translations.update({craftables[i]["abbev"]: i for i in craftables})

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
            Inventory varchar(255),
            Coins int,
            Potions varchar(255),
            PRIMARY KEY (UserID)
        );
        """)
        await db.commit()

async def encrypt_inventory(inventory):
    string = ""
    for key, value in inventory.items():
        if key == None:
            continue
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
        INSERT INTO Users (UserID, XP, Inventory, Coins, Potions)
        VALUES ({user_id}, 0, '', 0, '');
        """)
        await db.commit()

async def add_to_inventory(item, user_id):
    await check_user_exist(user_id)
    if item == None:
        return
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

async def remove_from_inventory(item, user_id):
    await check_user_exist(user_id)
    inventory = await decrypt_inventory(await get_inventory(user_id))
    try:
        inventory[item] = int(inventory[item])
        inventory[item] -= 1
        if inventory[item] <= 0:
            inventory.pop(item)
    except:
        pass
    encrypted = await encrypt_inventory(inventory)
    async with aiosqlite.connect(DB_URL) as db:
        await db.execute(f"""
        UPDATE Users
        SET Inventory = '{encrypted}'
        WHERE UserID = {user_id};
        """)
        await db.commit()

async def add_coins(amount, user_id):
    await check_user_exist(user_id)
    async with aiosqlite.connect(DB_URL) as db:
        cursor = await db.execute(f"""
        SELECT Coins FROM Users WHERE UserID = {user_id};
        """)
        coins = await cursor.fetchone()
        coins = coins[0] if coins[0] != None else 0
        coins += amount
        if coins < 0:
            coins = 0
        await db.execute(f"""
        UPDATE Users
        SET Coins = {coins}
        WHERE UserID = {user_id};
        """)
        await db.commit()

async def get_coins(user_id):
    await check_user_exist(user_id)
    async with aiosqlite.connect(DB_URL) as db:
        cursor = await db.execute(f"""
        SELECT Coins FROM Users WHERE UserID = {user_id};
        """)
        coins = await cursor.fetchone()
        return coins[0] if coins[0] != None else 0

async def remove_coins(amount, user_id):
    await check_user_exist(user_id)
    async with aiosqlite.connect(DB_URL) as db:
        cursor = await db.execute(f"""
        SELECT Coins FROM Users WHERE UserID = {user_id};
        """)
        coins = await cursor.fetchone()
        coins = coins[0] if coins[0] != None else 0
        coins -= amount
        if coins < 0:
            coins = 0
        await db.execute(f"""
        UPDATE Users
        SET Coins = {coins}
        WHERE UserID = {user_id};
        """)
        await db.commit()

async def empty_db():
    async with aiosqlite.connect(DB_URL) as db:
        await db.execute(f"""
        DROP TABLE IF EXISTS Users;
        """)
        await db.commit()

async def clear_inventory(user_id):
    await check_user_exist(user_id)
    async with aiosqlite.connect(DB_URL) as db:
        await db.execute(f"""
        UPDATE Users
        SET Inventory = ''
        WHERE UserID = {user_id};
        """)
        await db.commit()
    await clear_potions(user_id)
    await clear_craftables(user_id)

async def get_potions(user_id):
    await check_user_exist(user_id)
    async with aiosqlite.connect(DB_URL) as db:
        cursor = await db.execute(f"""
        SELECT Potions FROM Users WHERE UserID = {user_id};
        """)
        potions = await cursor.fetchone()
        if potions[0] == None:
            return ""
        return potions[0]

async def add_potion(potion, user_id):
    await check_user_exist(user_id)
    potions = await decrypt_inventory(await get_potions(user_id))
    try:
        potions[potion] = int(potions[potion])
        potions[potion] += 1
    except:
        potions[potion] = 1
    encrypted = await encrypt_inventory(potions)
    async with aiosqlite.connect(DB_URL) as db:
        await db.execute(f"""
        UPDATE Users
        SET Potions = '{encrypted}'
        WHERE UserID = {user_id};
        """)
        await db.commit()

async def remove_potion(potion, user_id):
    await check_user_exist(user_id)
    potions = await decrypt_inventory(await get_potions(user_id))
    potions[potion] = int(potions[potion])
    potions[potion] -= 1
    if potions[potion] <= 0:
        potions.pop(potion)
    encrypted = await encrypt_inventory(potions)
    async with aiosqlite.connect(DB_URL) as db:
        await db.execute(f"""
        UPDATE Users
        SET Potions = '{encrypted}'
        WHERE UserID = {user_id};
        """)
        await db.commit()

async def clear_potions(user_id):
    await check_user_exist(user_id)
    async with aiosqlite.connect(DB_URL) as db:
        await db.execute(f"""
        UPDATE Users
        SET Potions = ''
        WHERE UserID = {user_id};
        """)
        await db.commit()

async def get_xp(user_id):
    await check_user_exist(user_id)
    async with aiosqlite.connect(DB_URL) as db:
        cursor = await db.execute(f"""
        SELECT XP FROM Users WHERE UserID = {user_id};
        """)
        xp = await cursor.fetchone()
        return xp[0] if xp[0] != None else 0
    
async def add_xp(amount, user_id):
    await check_user_exist(user_id)
    async with aiosqlite.connect(DB_URL) as db:
        cursor = await db.execute(f"""
        SELECT XP FROM Users WHERE UserID = {user_id};
        """)
        xp = await cursor.fetchone()
        xp = xp[0] if xp[0] != None else 0
        xp += amount
        if xp < 0:
            xp = 0
        await db.execute(f"""
        UPDATE Users
        SET XP = {xp}
        WHERE UserID = {user_id};
        """)
        await db.commit()

async def remove_xp(amount, user_id):
    await check_user_exist(user_id)
    async with aiosqlite.connect(DB_URL) as db:
        cursor = await db.execute(f"""
        SELECT XP FROM Users WHERE UserID = {user_id};
        """)
        xp = await cursor.fetchone()
        xp = xp[0] if xp[0] != None else 0
        xp -= amount
        if xp < 0:
            xp = 0
        await db.execute(f"""
        UPDATE Users
        SET XP = {xp}
        WHERE UserID = {user_id};
        """)
        await db.commit()

async def add_column(column_name, column_type):
    async with aiosqlite.connect(DB_URL) as db:
        await db.execute(f"""
        ALTER TABLE Users
        ADD {column_name} {column_type};
        """)
        await db.commit()

async def get_craftables(user_id):
    await check_user_exist(user_id)
    async with aiosqlite.connect(DB_URL) as db:
        cursor = await db.execute(f"""
        SELECT Craftables FROM Users WHERE UserID = {user_id};
        """)
        craftables = await cursor.fetchone()
        if craftables[0] == None:
            return ""
        return craftables[0]

async def add_craftable(craftable, user_id):
    await check_user_exist(user_id)
    craftables = await decrypt_inventory(await get_craftables(user_id))
    try:
        craftables[craftable] = int(craftables[craftable])
        craftables[craftable] += 1
    except:
        craftables[craftable] = 1
    encrypted = await encrypt_inventory(craftables)
    async with aiosqlite.connect(DB_URL) as db:
        await db.execute(f"""
        UPDATE Users
        SET Craftables = '{encrypted}'
        WHERE UserID = {user_id};
        """)
        await db.commit()

async def clear_craftables(user_id):
    await check_user_exist(user_id)
    async with aiosqlite.connect(DB_URL) as db:
        await db.execute(f"""
        UPDATE Users
        SET Craftables = ''
        WHERE UserID = {user_id};
        """)
        await db.commit()

async def remove_craftable(craftable, user_id):
    await check_user_exist(user_id)
    craftables = await decrypt_inventory(await get_craftables(user_id))
    try:
        craftables[craftable] = int(craftables[craftable])
        craftables[craftable] -= 1
        if craftables[craftable] <= 0:
            craftables.pop(craftable)
    except:
        pass
    encrypted = await encrypt_inventory(craftables)
    async with aiosqlite.connect(DB_URL) as db:
        await db.execute(f"""
        UPDATE Users
        SET Craftables = '{encrypted}'
        WHERE UserID = {user_id};
        """)
        await db.commit()

async def remove_column(column_name):
    async with aiosqlite.connect(DB_URL) as db:
        await db.execute(f"""
        ALTER TABLE Users
        DROP COLUMN {column_name};
        """)
        await db.commit()

async def get_mutated(user_id):
    await check_user_exist(user_id)
    async with aiosqlite.connect(DB_URL) as db:
        cursor = await db.execute(f"""
        SELECT Mutated FROM Users WHERE UserID = {user_id};
        """)
        mutated = await cursor.fetchone()
        if mutated[0] == None:
            return ""
        return mutated[0]

async def add_mutated(mutated, user_id):
    await check_user_exist(user_id)
    mutated_list = await decrypt_inventory(await get_mutated(user_id))
    try:
        mutated_list[mutated] = int(mutated_list[mutated])
        mutated_list[mutated] += 1
    except:
        mutated_list[mutated] = 1
    encrypted = await encrypt_inventory(mutated_list)
    async with aiosqlite.connect(DB_URL) as db:
        await db.execute(f"""
        UPDATE Users
        SET Mutated = '{encrypted}'
        WHERE UserID = {user_id};
        """)
        await db.commit()

async def remove_mutated(mutated, user_id):
    await check_user_exist(user_id)
    mutated_list = await decrypt_inventory(await get_mutated(user_id))
    try:
        mutated_list[mutated] = int(mutated_list[mutated])
        mutated_list[mutated] -= 1
        if mutated_list[mutated] <= 0:
            mutated_list.pop(mutated)
    except:
        pass
    encrypted = await encrypt_inventory(mutated_list)
    async with aiosqlite.connect(DB_URL) as db:
        await db.execute(f"""
        UPDATE Users
        SET Mutated = '{encrypted}'
        WHERE UserID = {user_id};
        """)
        await db.commit()