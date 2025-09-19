import discord, json, random
from discord import app_commands
from discord.ext import commands

from database import *

with open("items.json", "r") as items:
    things = json.load(items)

sum = 0
roundTo = 1
small_value = 0.000000000000000000001 # Because .uniform method is exclusive of the last character

roll_group = discord.app_commands.Group(name="roll", description="Roll commands")

@roll_group.command(name="random", description="Roll a random item")
async def rand_roll(interaction: discord.Interaction):
    global sum
    spun = await spin()
    await add_to_inventory(spun, interaction.user.id)
    await interaction.response.send_message(f"You got a **{spun}** (*{things[spun]['chance']}%*)!")

@roll_group.command(name="inventory", description="Show your inventory")
async def inventory(interaction: discord.Interaction, user: discord.User=None):
    string = ""
    if user is None:
        user = interaction.user
    user_inven = await decrypt_inventory(await get_inventory(user.id))
    embed = discord.Embed(
        title=f"{user.name}'s Inventory",
        description="Completion: " + f"`{len(user_inven)}/{len(things)-1}`",
        color=discord.Color.blue()
    )
    embed.set_author(name=user.name, icon_url=user.display_avatar.url)
    for key, value in user_inven.items():
        string += f"**{key}** - x{value}\n"
    if string == "":
        string = "Your inventory is empty!"
    embed.add_field(name="Items", value=string)
    await interaction.response.send_message(embed=embed)

@roll_group.command(name="evolve", description="Evolve an item")
async def evolve(interaction: discord.Interaction, item: str):
    user_inven = await decrypt_inventory(await get_inventory(interaction.user.id))
    

async def spin():
    spin = round(random.uniform(0, 1), roundTo)
    spun = ""
    for i in things:
        if spin < things[i]["rarity"]:
            spun = things[i]["name"]
    return spun

async def calculate_rarities():
    global sum, roundTo
    for i in things:
        sum += things[i]["rarity"]
        if len(str(things[i]["rarity"]))-2 > roundTo:
            roundTo = len(str(things[i]["rarity"]))-2
    sum = round(sum, roundTo)