import discord, random, json
from discord import app_commands
from discord.ext import commands

async def msi(spinfn, user_id: int):
    return [await spinfn(user_id) for i in range(3)]