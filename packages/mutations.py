import discord
from discord.ext import commands
from discord import app_commands

from database import *

mutated_group = discord.app_commands.Group(name="mutations", description="Mutation commands")

@mutated_group.command(name="inventory", description="View your mutations inventory")
async def mutations_inventory(interaction: discord.Interaction):
    user_id = interaction.user.id
    raw = await get_mutated(user_id)
    inventory = await decrypt_inventory(raw)
    embed = discord.Embed(title=f"{interaction.user.name}'s Mutations Inventory", color=discord.Color.green())
    if inventory:
        temp = ""
        for item, quantity in inventory.items():
            temp += f"**({quantity}) {item}**\n"
        embed.add_field(name="Mutations", value=temp, inline=False)
    else:
        embed.add_field(name="Empty", value="You have no mutations in your inventory.", inline=False)
    await interaction.response.send_message(embed=embed)