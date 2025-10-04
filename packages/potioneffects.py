import discord, random, json
from discord import app_commands
from discord.ext import commands

from database import *

async def msi(spinfn, user_id: int):
    return [await spinfn(user_id) for i in range(3)]

async def transmutate1(spinfn, user_id: int):
    result = await spinfn(user_id, transmutate_amount=1)
    return [result]

async def transmutate2(spinfn, user_id: int):
    result = await spinfn(user_id, transmutate_amount=2)
    return [result]

async def transmutate3(spinfn, user_id: int):
    result = await spinfn(user_id, transmutate_amount=3)
    return [result]

async def l1(spinfn, user_id: int):
    return [await spinfn(user_id, potion_strength=2)]

async def l2(spinfn, user_id: int):
    return [await spinfn(user_id, potion_strength=3)]

async def l3(spinfn, user_id: int):
    return [await spinfn(user_id, potion_strength=5)]

async def msii(spinfn, user_id: int):
    return [await spinfn(user_id) for i in range(5)]

async def msiii(spinfn, user_id: int):
    return [await spinfn(user_id) for i in range(10)]

async def xpbottle(xpfn, user_id: int):
    await xpfn(300, user_id)
    return ["You gained **100 XP**!"]

async def godly(spinfn, user_id: int):
    return [await spinfn(user_id, potion_strength=50)]