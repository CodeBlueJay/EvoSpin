import discord, json, random, math
from discord import app_commands
from discord.ext import commands

from database import *
import packages.potioneffects as potioneffects

with open("configuration/items.json", "r") as items:
    things = json.load(items)
with open("configuration/settings.json", "r") as settings:
    settings = json.load(settings)
with open("configuration/crafting.json", "r") as craftables:
    craft = json.load(craftables)

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
                await interaction.response.send_message(f"You evolved **{things[item.title()]['required'] * amount} {item.title()}** into **{amount} {things[item.title()]['next_evo']}**!")
                for i in range(things[item.title()]["required"] * amount):
                    await remove_from_inventory(item.title(), interaction.user.id)
            else:
                await interaction.response.send_message(f"You need at least **{things[item.title()]['required'] * amount}** **{item.title()}** to evolve it!")
                return

async def spin(user_id, item: str=None, transmutate_amount: int=0, potion_strength: float=0.0):
    spun = ""
    temp = ""
    xp = await get_xp(user_id)
    xp_scale = settings.get("xp_scale", 25000)
    max_luck_strength = settings.get("max_luck_strength", 0.8)
    potion_exponent_factor = settings.get("potion_exponent_factor", 0.5)
    if xp_scale <= 0:
        xp_scale = 1
    progress = 1 - math.exp(-xp / xp_scale)
    luck_strength = progress * max_luck_strength
    exponent_base = 1 - luck_strength
    exponent_final = exponent_base * (1 - potion_strength * potion_exponent_factor)
    if exponent_final < 0.12:
        #exponent_final = 0.12
        pass
    population = [things[i]["name"] for i in things if things[i]["rarity"] > 0]
    weights = [things[i]["rarity"] for i in things if things[i]["rarity"] > 0]
    transformed_weights = [w ** exponent_final for w in weights]
    spun = random.choices(population, weights=transformed_weights, k=1)[0]
    total = sum(weights)
    if transmutate_amount > 0:
        for i in range(transmutate_amount):
            temp = things[spun]["name"]
            spun = things[spun]["next_evo"]
            if spun == None:
                spun = temp
    if item != None:
        spun = item.title()
    await add_to_inventory(spun, user_id)
    await add_xp(1, user_id)
    try:
        return f"You got a **{spun}** (*1 in {'{:,}'.format(round((total / things[spun]['rarity'])))}*)!"
    except:
        return f"You got a **{spun}** (*1 in 0*)!"

@roll_group.command(name="use_potion", description="Use a potion to increase your chances")
async def use_potion(interaction: discord.Interaction, potion: str, amount: int=1):
    potion_functions = {
        "Multi-Spin 1": lambda user_id: potioneffects.msi(spin, user_id),
        "Transmutate 1": lambda user_id: potioneffects.transmutate1(spin, user_id),
        "Luck 1": lambda user_id: potioneffects.l1(spin, user_id),
        "Luck 2": lambda user_id: potioneffects.l2(spin, user_id),
        "Luck 3": lambda user_id: potioneffects.l3(spin, user_id),
        "Multi-Spin 2": lambda user_id: potioneffects.msii(spin, user_id),
        "Multi-Spin 3": lambda user_id: potioneffects.msiii(spin, user_id),
        "Xp Bottle": lambda user_id: potioneffects.xpbottle(add_xp, user_id),
        "Godly": lambda user_id: potioneffects.godly(spin, user_id),
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

@roll_group.command(name="inventory", description="Show your inventory")
async def inventory(interaction: discord.Interaction, user: discord.User=None):
    user_inven = await decrypt_inventory(await get_inventory(user.id if user else interaction.user.id))
    potion_inven = await decrypt_inventory(await get_potions(user.id if user else interaction.user.id))
    craftables = await decrypt_inventory(await get_craftables(user.id if user else interaction.user.id))
    potion_string = ""
    self = True
    if user == None:
        user = interaction.user
    else:
        self = False
    user_inven = await decrypt_inventory(await get_inventory(user.id if user else interaction.user.id))
    number_of_comp = 0
    for key in things:
        if things[key]["comp"]:
            number_of_comp += 1
    embed = discord.Embed(
        title=f"{user.name}'s Inventory",
        description=f"Completion: `{len(user_inven)}/{number_of_comp}` (`{round(len(user_inven)/number_of_comp * 100, 2)}%`)\nXP: `{await get_xp(user.id if user else interaction.user.id)}`",
        color=discord.Color.purple()
    )
    embed.set_author(name=user.name, icon_url=user.display_avatar.url)
    temp = ""
    embed.add_field(name="Coins", value=f"`{await get_coins(user.id)}`", inline=False)
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
                    temp += f"**({user_inven[j]}) {j}**"
                else:
                    temp += j
                if not j == i[-1]:
                    temp += " > "
            temp += "\n"
    def add_chunked_fields(embed_obj: discord.Embed, base_name: str, text: str, inline=False):
        text = text.rstrip('\n')
        if len(text) <= 1024:
            embed_obj.add_field(name=base_name, value=text if text else "(Empty)", inline=inline)
            return
        lines = text.split('\n')
        current = ""
        idx = 1
        for line in lines:
            projected = (len(current) + (1 if current else 0) + len(line))
            if projected > 1024:
                embed_obj.add_field(name=f"{base_name}", value=current or "(Empty)", inline=inline)
                current = line
                idx += 1
            else:
                current = line if not current else current + "\n" + line
        if current:
            embed_obj.add_field(name=f"{base_name}", value=current, inline=inline)
    add_chunked_fields(embed, "Inventory", temp or "(Empty)", inline=False)
    craft_string = "".join(f"**({craftables[key]}) {key}**\n" for key in craftables)
    if craft_string == "":
        craft_string = "You have no craftable items!" if self == True else f"{user.name} has no craftable items!"
    add_chunked_fields(embed, "Craftables", craft_string, inline=False)
    for key, value in potion_inven.items():
        potion_string += f"**({value}) {key}**\n"
    if potion_string == "":
        potion_string = "You have no potions!" if self == True else f"{user.name} has no potions!"
    add_chunked_fields(embed, "Potions", potion_string, inline=False)
    if len(embed.fields) > 25:
        full_text = "INVENTORY\n" + (temp or "(Empty)") + "\n\nCRAFTABLES\n" + craft_string + "\n\nPOTIONS\n" + potion_string
        file = discord.File(fp=discord.utils._BytesIO(full_text.encode('utf-8')), filename="inventory.txt")
        await interaction.response.send_message(content="Inventory too large, sent as file instead.", file=file)
    else:
        await interaction.response.send_message(embed=embed)

@roll_group.command(name="info", description="Show an item's info")
async def item_info(interaction: discord.Interaction, item: str):
    item = item.title()
    if not item in things and not item in craft:
        await interaction.response.send_message("That item does not exist!")
        return
    if item in craft:
        data = craft[item]
    else:
        data = things[item]
    embed = discord.Embed(
        title=f"{item} Info",
        color=discord.Color.blue()
    )
    # embed.set_thumbnail(url=data.get("image", ""))
    if data["rarity"] > 0 and data["rarity"] != None:
        temp = f"1 in {round((totalsum / data['rarity']))}"
    elif data["rarity"] == 0:
        temp = "Evolution"
    else:
        temp = "Craftable"
    embed.add_field(name="Rarity", value=temp, inline=True)
    embed.add_field(name="Value", value=f"{str(data['worth'])} coins" if data['worth'] != None else "0", inline=True)
    if data["rarity"] == 0:
        embed.add_field(name="Obtainment", value=f"Evolution", inline=True)
    elif data["comp"] == "Craftable":
        embed.add_field(name="Obtainment", value="Craftable", inline=True)
    elif data["comp"] != None:
        embed.add_field(name="Obtainment", value="Natural", inline=True)
    if data["next_evo"] != None:
        embed.add_field(name="Next Evolution", value=f"{data['next_evo']} (Requires {data['required']})", inline=True)
    else:
        embed.add_field(name="Next Evolution", value="None", inline=True)
    if data["prev_evo"] != None:
        embed.add_field(name="Previous Evolution", value=f"{data['prev_evo']}", inline=True)
    else:
        embed.add_field(name="Previous Evolution", value="None", inline=True)
    if data.get("description", None) != None:
        embed.add_field(name="Description", value=data["description"], inline=False)
    await interaction.response.defer(thinking=True)
    await interaction.followup.send(embed=embed)

async def calculate_rarities():
    global totalsum, roundTo
    for i in things:
        totalsum += things[i]["rarity"]
        if len(str(things[i]["rarity"]))-2 > roundTo:
            roundTo = len(str(things[i]["rarity"]))-2
    totalsum = round(totalsum, roundTo)