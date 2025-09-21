import discord, json, random
from discord import app_commands
from discord.ext import commands

from database import *
import packages.potioneffects as potioneffects

with open("configuration/items.json", "r") as items:
    things = json.load(items)
with open("configuration/settings.json", "r") as settings:
    settings = json.load(settings)

totalsum = 0
roundTo = 1
small_value = 0.000000000000000000001 # Because .uniform method is exclusive of the last character

roll_group = discord.app_commands.Group(name="roll", description="Roll commands")

@roll_group.command(name="random", description="Roll a random item")
@app_commands.checks.cooldown(1, settings["cooldown"], key=lambda i: i.user.id)
async def rand_roll(interaction: discord.Interaction):
    await interaction.response.send_message(await spin(interaction.user.id))

@rand_roll.error
async def rand_roll_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(f"Slow down, you're on cooldown.", ephemeral=True)

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
    embed.add_field(name="Coins", value=f"**`{await get_coins(user.id)}`**", inline=False)
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
                for i in range(amount):
                    await add_to_inventory(things[item.title()]["next_evo"], interaction.user.id)
                await interaction.response.send_message(f"You evolved **{things[item.title()]["required"] * amount} {item.title()}** into **{amount} {things[item.title()]['next_evo']}**!")
                for i in range(things[item.title()]["required"] * amount):
                    await remove_from_inventory(item.title(), interaction.user.id)
            else:
                await interaction.response.send_message(f"You need at least **{things[item.title()]['required'] * amount}** **{item.title()}** to evolve it!")
                return

async def spin(user_id, item: str=None, transmutate: bool=False):
    spun = ""
    temp = ""
    population = [things[i]["name"] for i in things if things[i]["rarity"] > 0]
    weights = [things[i]["rarity"] for i in things if things[i]["rarity"] > 0]
    spun = random.choices(population, weights=weights, k=1)[0]
    total = sum(weights)
    if transmutate:
        temp = things[spun]["name"]
        spun = things[spun]["next_evo"]
        if spun == None:
            spun = temp
    if item != None:
        spun = item.title()
    await add_to_inventory(spun, user_id)
    try:
        return f"You got a **{spun}** (*1 in {round((total / things[spun]['rarity']))}*)!"
    except:
        return f"You got a **{spun}** (*1 in 0*)!"

@roll_group.command(name="use_potion", description="Use a potion to increase your chances")
async def use_potion(interaction: discord.Interaction, potion: str, amount: int=1):
    potion_functions = {
        "Multi-Spin I": lambda user_id: potioneffects.msi(spin, user_id),
        "Transmutate": lambda user_id: potioneffects.transmutate(spin, user_id)
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
            await interaction.response.send_message(f"You used **{amount} {potion}**!")
            for i in range(amount):
                await remove_potion(potion, interaction.user.id)
                action = potion_functions.get(potion)
                temp = ""
                for j in await action(interaction.user.id):
                    temp += j + "\n"
                await interaction.followup.send(temp)
        else:
            await interaction.response.send_message("You do not have that potion!")

@roll_group.command(name="completion", description="Show your completion info")
async def completion(interaction: discord.Interaction, user: discord.User=None):
    self = True
    if user == None:
        user = interaction.user
    else:
        self = False
    user_inven = await decrypt_inventory(await get_inventory(user.id))
    number_of_comp = 0
    for key in things:
        if things[key]["comp"]:
            number_of_comp += 1
    embed = discord.Embed(
        title=f"{user.name}'s Completion Info",
        description="Completion: " + f"`{len(user_inven)}/{number_of_comp}` " + f"(`{round(len(user_inven)/number_of_comp * 100, 2)}%`)",
        color=discord.Color.purple()
    )
    embed.set_author(name=user.name, icon_url=user.display_avatar.url)
    temp = ""
    if False:
        embed.add_field(name="Info", value="You have no items in your inventory!" if self == True else f"{user.name} has no items in their inventory!", inline=False)
        await interaction.response.send_message(embed=embed)
        return
    else:
        temp_things = things.copy()
        evolution_chains = []
        keys = list(temp_things.keys())
        for key in keys:
            data = temp_things[key]
            if data["comp"]:
                if data["next_evo"] != None and data["prev_evo"] == None:
                    temp_list = []
                    while data["next_evo"] != None:
                        temp_list.append(data["name"])
                        data = temp_things[data["next_evo"]]
                    temp_list.append(data["name"])
                    evolution_chains.append(temp_list)
                else:
                    if data["prev_evo"] == None:
                        evolution_chains.append([temp_things[key]["name"]])
        for i in evolution_chains:
            for j in i:
                if j in user_inven:
                    temp += f"**{j}**"
                else:
                    temp += j
                if not j == i[-1]:
                    temp += " > "
            temp += "\n"
    embed.add_field(name="Info", value="**Owned**/Not Owned\n\n" + temp, inline=True)
    await interaction.response.send_message(embed=embed)

async def calculate_rarities():
    global totalsum, roundTo
    for i in things:
        totalsum += things[i]["rarity"]
        if len(str(things[i]["rarity"]))-2 > roundTo:
            roundTo = len(str(things[i]["rarity"]))-2
    totalsum = round(totalsum, roundTo)