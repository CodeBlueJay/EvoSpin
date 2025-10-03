import discord
from discord.ext import commands
from discord import app_commands
from database import *

trade_group = discord.app_commands.Group(name="trade", description="Trading commands")

@trade_group.command(name="", description="")