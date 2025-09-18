import discord
from discord import app_commands
from discord.ext import commands

roll_group = discord.app_commands.Group(name="roll", description="Roll commands")

@roll_group.command(name="random", description="Roll a random item")
async def rand_roll(interaction: discord.Interaction):
    await interaction.response.send_message("Success")