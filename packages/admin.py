import discord, json, random
from discord import app_commands
from discord.ext import commands

from database import *
from packages.roll import spin

with open("configuration/items.json", "r") as items:
    things = json.load(items)

admin_group = discord.app_commands.Group(name="admin", description="Admin commands")

@admin_group.command(name="roll", description="Admin type command :fire:")
async def roll_amount(interaction: discord.Interaction, amount: int):
    if interaction.user.id != 908954867962380298:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    temp = ""
    for i in range(amount):
        spun = await spin()
        await add_to_inventory(spun, interaction.user.id)
        temp += f"You got a **{spun}**! (*{things[spun]['chance']}%*)\n"
    try:
        await interaction.response.send_message(temp)
    except:
        await interaction.response.send_message("Complete")

@admin_group.command(name="give_item", description="Give an item to a user")
async def give(interaction: discord.Interaction, user: discord.User, item: str, amount: int=1):
    if interaction.user.id != 908954867962380298:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    for i in range(amount):
        await add_to_inventory(item.title(), user.id)
    await interaction.response.send_message(f"Gave **{amount}** **{item.title()}** to {user.name}!")

@admin_group.command(name="give_coins", description="Give coins to a user")
async def give_coins(interaction: discord.Interaction, user: discord.User, amount: int):
    if interaction.user.id != 908954867962380298:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    await add_coins(amount, user.id)
    await interaction.response.send_message(f"Added **{amount}** coins to {user.name}!")

@admin_group.command(name="reset_db", description="Empty the database")
async def empty_db_cmd(interaction: discord.Interaction):
    if interaction.user.id != 908954867962380298:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    await empty_db()
    await init_db()
    await interaction.response.send_message("Reset the database!")

@admin_group.command(name="clear_inventory", description="Clear a user's inventory")
async def clear_inventory_cmd(interaction: discord.Interaction, user: discord.User):
    if interaction.user.id != 908954867962380298:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    await clear_inventory(user.id)
    await interaction.response.send_message(f"Cleared {user.name}'s inventory!")

@admin_group.command(name="give_potion", description="Give a potion to a user")
async def give_potion(interaction: discord.Interaction, user: discord.User, potion: str, amount: int=1 ):
    if interaction.user.id != 908954867962380298:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    for i in range(amount):
        await add_potion(potion.title(), user.id)
    await interaction.response.send_message(f"Gave **{amount}** **{potion.title()}** to {user.name}!")

@admin_group.command(name="clear_potions", description="Clear a user's potions")
async def clear_potions(interaction: discord.Interaction, user: discord.User):
    if interaction.user.id != 908954867962380298:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    await clear_potions(user.id)
    await interaction.response.send_message(f"Cleared {user.name}'s potions!")