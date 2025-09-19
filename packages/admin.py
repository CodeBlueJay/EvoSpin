import discord, json, random
from discord import app_commands
from discord.ext import commands

from database import *
from packages.roll import spin

with open("items.json", "r") as items:
    things = json.load(items)

admin_group = discord.app_commands.Group(name="admin", description="Admin commands")

@admin_group.command(name="roll_10k", description="Admin type command :fire:")
async def roll10(interaction: discord.Interaction):
    if interaction.user.id != 908954867962380298:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    temp = ""
    for i in range(10000):
        spun = await spin()
        await add_to_inventory(spun, interaction.user.id)
        temp += f"You got a **{spun}**!\n"
    try:
        await interaction.followup.send(temp)
    except:
        await interaction.followup.send("Complete")

@admin_group.command(name="give", description="Give an item to a user")
async def give(interaction: discord.Interaction, user: discord.User, item: str):
    if interaction.user.id != 908954867962380298:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    await add_to_inventory(item.title(), user.id)
    await interaction.response.send_message(f"Gave **{item.title()}** to {user.name}!")
