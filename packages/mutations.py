import discord
from discord.ext import commands
from discord import app_commands

from database import *

mutated_group = discord.app_commands.Group(name="mutations", description="Mutation commands")

@mutated_group.command(name="inventory", description="View your mutations inventory")
async def mutations_inventory(interaction: discord.Interaction):
    user_id = interaction.user.id
    inventory = await get_mutated(user_id)
    embed = discord.Embed(title=f"{interaction.user.name}'s Mutations Inventory", color=discord.Color.green())
    if inventory:
        for item, quantity in inventory.items():
            embed.add_field(name=item, value=f"Quantity: {quantity}", inline=False)
    else:
        embed.add_field(name="Empty", value="You have no mutations in your inventory.", inline=False)
    await interaction.response.send_message(embed=embed)