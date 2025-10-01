import discord
from discord import app_commands
from discord.ext import commands
from database import *

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
        embed.add_field(name=i, value=f"Ingredients: {components}\nDescription: *{craftables[i]['description']}*\nValue: **`{craftables[i]['value']}`**", inline=False)
    await interaction.response.send_message(embed=embed)
