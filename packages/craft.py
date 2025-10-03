import discord
from discord import app_commands
from discord.ext import commands
from database import *

from packages.roll import spin

with open("configuration/crafting.json", "r") as craftfile:
    craftables = json.load(craftfile)

craft_group = discord.app_commands.Group(name="craft", description="Crafting commands")

@craft_group.command(name="item", description="Craft an item using components")
async def craft(interaction: discord.Interaction, item: str, amount: int=1):
    user_inven = await decrypt_inventory(await get_inventory(interaction.user.id))
    item = item.title()
    if item not in craftables:
        await interaction.response.send_message(f"**{item}** is not a craftable item!")
        return
    for i in craftables[item]["components"]:
        if int(user_inven[i]) < craftables[item]["components"][i] * amount:
            await interaction.response.send_message(f"You need at least **{craftables[item]['components'][i] * amount} {i}** to craft **{amount} {item}**!")
            return
    for i in craftables[item]["components"]:
        for j in range(craftables[item]["components"][i] * amount):
            await remove_from_inventory(i, interaction.user.id)
    for i in range(amount):
        await add_craftable(item, interaction.user.id)
    await interaction.response.send_message(f"You crafted **{amount} {item}**!")

@craft_group.command(name="list", description="List all craftable items")
async def craft_list(interaction: discord.Interaction):
    embed = discord.Embed(title="Craftable Items", color=discord.Color.blue())
    for i in craftables:
        components = ""
        for j in craftables[i]["components"]:
            components += f"**{craftables[i]['components'][j]} {j}**, "
        components = components[:-2]
        embed.add_field(name=i, value=f"Ingredients: {components}\nDescription: *{craftables[i]['description']}*\nValue: **`{craftables[i]['worth']}`**", inline=False)
    await interaction.response.send_message(embed=embed)

@craft_group.command(name="concoct", description="Concoct a potion with different effects")
async def concoct(interaction: discord.Interaction, luck: float=0, multi_spin: int=0, transmutate: int=0):
    if luck == multi_spin == transmutate == 0:
        await interaction.response.send_message("You must choose at least one modifier!")
        return
    total_cost = 0
    if luck > 3:
        await interaction.response.send_message("Luck cannot be greater than 3!")
    else:
        total_cost += luck
    if multi_spin > 3:
        await interaction.response.send_message("Multi-spin cannot be greater than 3!")
    else:
        total_cost += multi_spin
    if transmutate > 5:
        await interaction.response.send_message("Transmutate cannot be greater than 5!")
    else:
        total_cost += transmutate
    multiplier = luck + multi_spin + transmutate
    total_cost = int(5000 * (1 + (multiplier * 0.5)))
    await remove_xp(total_cost, interaction.user.id)
    temp = ""
    for i in range(multi_spin):
        spun = await spin(interaction.user.id, potion_strength=luck, transmutate_amount=transmutate)
        temp += spun + "\n"
    await interaction.response.send_message(f"Concocted a potion with **{luck}** luck, **{multi_spin}** multi-spin, and **{transmutate}** transmutation")
    await interaction.followup.send(temp)
