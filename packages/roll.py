import discord, json, random
from discord import app_commands
from discord.ext import commands

from database import add_to_inventory

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