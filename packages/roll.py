import discord, json, random
from discord import app_commands
from discord.ext import commands

from database import *

with open("configuration/items.json", "r") as items:
    things = json.load(items)

sum = 0
roundTo = 1
small_value = 0.000000000000000000001 # Because .uniform method is exclusive of the last character

roll_group = discord.app_commands.Group(name="roll", description="Roll commands")

@roll_group.command(name="random", description="Roll a random item")
async def rand_roll(interaction: discord.Interaction):
    global sum
    await interaction.response.send_message(await spin(interaction.user.id))

@roll_group.command(name="inventory", description="Show your inventory")
async def inventory(interaction: discord.Interaction, user: discord.User=None):
    inven_string = ""
    potion_string = ""
    self = True
    if user == None:
        user = interaction.user
    else:
        self = False
    user_inven = await decrypt_inventory(await get_inventory(user.id))
    potion_inven = await decrypt_inventory(await get_potions(user.id))
    number_of_comp = 0
    for key in things:
        if things[key]["comp"]:
            number_of_comp += 1
    embed = discord.Embed(
        title=f"{user.name}'s Inventory",
        description="Completion: " + f"`{len(user_inven)}/{number_of_comp}`",
        color=discord.Color.blue()
    )
    embed.set_author(name=user.name, icon_url=user.display_avatar.url)
    embed.add_field(name="Coins", value=f"***{await get_coins(user.id)}***", inline=False)
    for key, value in user_inven.items():
        inven_string += f"**{key}** - x{value}\n"
    if inven_string == "":
        inven_string = "Your inventory is empty!" if self == True else f"{user.name}'s inventory is empty!"
    embed.add_field(name="Items", value=inven_string, inline=False)
    for key, value in potion_inven.items():
        potion_string += f"**{key}** - x{value}\n"
    if potion_string == "":
        potion_string = "You have no potions!" if self == True else f"{user.name} has no potions!"
    embed.add_field(name="Potions", value=potion_string, inline=False)
    await interaction.response.send_message(embed=embed)

@roll_group.command(name="evolve", description="Evolve an item")
async def evolve(interaction: discord.Interaction, item: str, amount: int=1):
    user_inven = await decrypt_inventory(await get_inventory(interaction.user.id))
    if things[item.title()]["next_evo"] == None:
        await interaction.response.send_message(f"**{item.title()}** cannot be evolved!")
        return
    else:
        if item.title() in user_inven:
            if int(user_inven[item.title()]) >= things[item.title()]["required"] * amount:
                user_inven[item.title()] = str(int(user_inven[item.title()]) - things[item.title()]["required"] * amount)
                if user_inven[item.title()] == "0":
                    user_inven.pop(item.title())
                await add_to_inventory(things[item.title()]["next_evo"], interaction.user.id)
                await interaction.response.send_message(f"You evolved **{item.title()}** into **{things[item.title()]['next_evo']}**!")
                for i in range(things[item.title()]["required"] * amount - 1):
                    await remove_from_inventory(item.title(), interaction.user.id)
            else:
                await interaction.response.send_message(f"You need at least **{things[item.title()]['required'] * amount}** **{item.title()}** to evolve it!")
                return

async def spin(user_id):
    spin = round(random.uniform(0, 1), roundTo)
    spun = ""
    temp = ""
    for i in things:
        if spin < things[i]["rarity"]:
            spun = things[i]["name"]
    await add_to_inventory(spun, user_id)
    return f"You got a **{spun}** (*{things[spun]['chance']}%*)!"

@roll_group.command(name="use_potion", description="Use a potion to increase your chances")
async def use_potion(interaction: discord.Interaction, potion: str):
    potion_functions = {
        "Multi-Spin I": [await spin(interaction.user.id) for i in range(3)]
    }
    potion = potion.title()
    potion_inven = await decrypt_inventory(await get_potions(interaction.user.id))
    if not potion in potion_inven:
        await interaction.response.send_message("You do not have that potion!")
    else:
        if int(potion_inven[potion]) > 0:
            potion_inven[potion] = str(int(potion_inven[potion]) - 1)
            if potion_inven[potion] == "0":
                potion_inven.pop(potion)
            await remove_potion(potion, interaction.user.id)
            await interaction.response.send_message(f"You used a **{potion}**!")
            action = potion_functions.get(potion)
            temp = ""
            for i in action:
                temp += i + "\n"
            await interaction.followup.send(temp)
        else:
            await interaction.response.send_message("You do not have that potion!")

async def calculate_rarities():
    global sum, roundTo
    for i in things:
        sum += things[i]["rarity"]
        if len(str(things[i]["rarity"]))-2 > roundTo:
            roundTo = len(str(things[i]["rarity"]))-2
    sum = round(sum, roundTo)