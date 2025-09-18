import discord, os
from discord import app_commands
from dotenv import load_dotenv

intents = discord.Intents.default()
intents.message_content = True

load_dotenv()
TOKEN = os.getenv("TOKEN")

bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    print(f"{bot.user} connected")

bot.run(TOKEN)