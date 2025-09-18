import discord, os, asyncio
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from database import init_db

from commands import *

intents = discord.Intents.default()
intents.message_content = True

load_dotenv()
TOKEN = os.getenv("TOKEN")

bot = commands.Bot(command_prefix="!", intents=intents)

async def load_commands():
    bot.tree.add_command(roll_group)
    synced = await bot.tree.sync()
    print(f"Synced {len(synced)} commands")

@bot.event
async def on_ready():
    print(f"{bot.user} connected")
    await init_db()
    print("Updated table: users")
    await load_commands()

bot.run(TOKEN)