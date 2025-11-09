import discord
from discord.ext import commands
from discord import app_commands

from database import *

mutated_group = discord.app_commands.Group(name="mutations", description="Mutation commands")