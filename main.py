import discord, os, asyncio
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from database import *

module = {}
for file in os.listdir("packages"):
    if not(file.startswith("_")):
        filename = file[:-3]
        module[filename] = __import__(f"packages.{filename}", fromlist=[filename])

intents = discord.Intents.default()
intents.message_content = True

load_dotenv()
TOKEN = os.getenv("TOKEN")

bot = commands.Bot(command_prefix="!", intents=intents)

cogs = [
    module["roll"].roll_group,
    module["admin"].admin_group,
    module["shop"].shop_group,
    module["craft"].craft_group,
    module["trade"].trade_group,
    module["mutations"].mutated_group
]

async def get_user(user_id):
    user = await bot.fetch_user(user_id)
    return user.name

async def load_commands():
    commands = ""
    for i in cogs:
        bot.tree.add_command(i)
        commands += f"{i.name}, "
    synced = await bot.tree.sync()
    print(f"Synced {len(synced)} commands: {commands[:-2]}")

@bot.event
async def on_ready():
    # await test_db()
    await init_db()
    await module["roll"].calculate_rarities()
    print(f"{bot.user} connected")
    await load_commands()

bot.run(TOKEN)