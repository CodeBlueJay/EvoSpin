import discord, os, asyncio
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from database import init_db, test_db

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

cogs = [module["roll"].roll_group]

async def load_commands():
    for i in cogs:
        bot.tree.add_command(i)
    synced = await bot.tree.sync()
    print(f"Synced {len(synced)} commands")

@bot.event
async def on_ready():
    # await test_db()
    await module["roll"].calculate_rarities()
    print(f"{bot.user} connected")
    await init_db()
    await load_commands()

bot.run(TOKEN)