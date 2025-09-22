import discord, random, json
from discord import app_commands
from discord.ext import commands

from database import *

async def msi(spinfn, user_id: int):
    return [await spinfn(user_id) for i in range(3)]

async def transmutate(spinfn, user_id: int):
    result = await spinfn(user_id, transmutate=True)
    return [result]

async def l1(spinfn, user_id: int):
    return [await spinfn(user_id, potion_strength=1.1)]

async def l2(spinfn, user_id: int):
    return [await spinfn(user_id, potion_strength=1.3)]

async def l3(spinfn, user_id: int):
    return [await spinfn(user_id, potion_strength=1.5)]

async def msii(spinfn, user_id: int):
    return [await spinfn(user_id) for i in range(5)]

async def msiii(spinfn, user_id: int):
    return [await spinfn(user_id) for i in range(10)]

async def xp(user_id: int):
    return await add_xp(user_id, 500)