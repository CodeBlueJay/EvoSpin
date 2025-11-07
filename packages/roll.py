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
with open("configuration/shop.json", "r") as shopf:
    potions_list = json.load(shopf)

lucky3 = False
lucky2x = False
active_event = None
event_messages = {
    "Galaxy": "\n✨ This item is from the Galaxy event! ✨",
    "Winter Wonderland": "\n❄️ You rolled a Winter Wonderland exclusive! ❄️",
}

totalsum = 0
roundTo = 1
small_value = 0.000000000000000000001 # Because .uniform method is exclusive of the last character

roll_group = discord.app_commands.Group(name="roll", description="Roll commands")

catch_multiplier = 1

@roll_group.command(name="random", description="Roll a random item")
@app_commands.checks.cooldown(1, settings["cooldown"], key=lambda i: i.user.id)
async def rand_roll(interaction: discord.Interaction):
    global lucky3, lucky2x
    current_multiplier = 3 if lucky3 else 1

    temp = ""
    for _ in range(current_multiplier):
        temp += await spin(interaction.user.id, potion_strength=0.0) + "\n"
    await interaction.response.send_message(temp)

@rand_roll.error
async def rand_roll_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(f"Slow down, you're on cooldown.", ephemeral=True)

@roll_group.command(name="evolve", description="Evolve an item")
async def evolve(interaction: discord.Interaction, item: str, amount: int=1):
    await interaction.response.defer()
    user_inven = await decrypt_inventory(await get_inventory(interaction.user.id))
    item_name = item.title()
    if item_name not in things:
        await interaction.followup.send("That item does not exist!")
        return
    if things[item_name].get("next_evo") is None:
        await interaction.followup.send(f"**{item_name}** cannot be evolved!")
        return
    if item_name not in user_inven:
        await interaction.followup.send(f"You don't have any **{item_name}** to evolve!")
        return
    required_total = things[item_name]["required"] * amount
    try:
        user_count = int(user_inven[item_name])
    except Exception:
        user_count = 0
    if user_count < required_total:
        await interaction.followup.send(f"You need at least **{required_total} {item_name}** to evolve it!")
        return
    user_inven[item_name] = str(user_count - required_total)
    if user_inven[item_name] == "0":
        user_inven.pop(item_name)
    for _ in range(amount):
        await add_to_inventory(things[item_name]["next_evo"], interaction.user.id)
    await interaction.followup.send(f"You evolved **{required_total} {item_name}** into **{amount} {things[item_name]['next_evo']}**!")
    for _ in range(required_total):
        await remove_from_inventory(item_name, interaction.user.id)

async def spin(user_id, item: str=None, transmutate_amount: int=0, potion_strength: float=0.0, mutation_chance: int=1, catch_multiplier=catch_multiplier):
    spun = ""
    spun_name = ""
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
    if potion_strength and potion_strength > 0:
        effective_potion_strength = potion_strength
    else:
        effective_potion_strength = 1.0

    if lucky2x:
        effective_potion_strength = effective_potion_strength * 2.0

    exponent_final = exponent_base * (1 - effective_potion_strength * potion_exponent_factor)
    if exponent_final < 0.1:
        exponent_final = 0.1
    population = []
    weights = []
    for k, v in things.items():
        item_event = v.get("event")
        if v.get("rarity", 0) > 0 and (item_event is None or item_event == active_event):
            population.append(v["name"])
            weights.append(v["rarity"])
    transformed_weights = [w ** exponent_final for w in weights]
    spun = random.choices(population, weights=transformed_weights, k=1)[0]
    spun_name = things[spun]["name"]
    total = sum(weights)
    if item != None:
        spun = item.title()
        spun_name = spun
    if transmutate_amount > 0:
        for i in range(transmutate_amount):
            temp = things[spun]["name"]
            spun = things[spun]["next_evo"]
            if spun == None:
                spun = temp
    spun_name = spun
    mutated = False
    mutations = things.get(spun, {}).get("mutations")
    # Support event-specific mutations by filtering candidates by their 'event' metadata
    if mutations and random.randint(1, 100) <= mutation_chance:
        candidates = []
        cand_weights = []
        # Mutations can be a dict {name: {weight, event, ...}} or a list of names/dicts
        if isinstance(mutations, dict):
            for name, spec in mutations.items():
                if isinstance(spec, dict):
                    mut_event = spec.get("event")
                    # If a mutation specifies an event, only allow it when active
                    if mut_event and mut_event != active_event:
                        continue
                    w = float(spec.get("weight", 1))
                else:
                    # Backward compatibility: plain value treated as weight=1, no event gate
                    w = 1.0
                candidates.append(name)
                cand_weights.append(max(0.0, w))
        elif isinstance(mutations, list):
            for entry in mutations:
                if isinstance(entry, dict):
                    name = entry.get("name")
                    if not name:
                        continue
                    mut_event = entry.get("event")
                    if mut_event and mut_event != active_event:
                        continue
                    w = float(entry.get("weight", 1))
                    candidates.append(name)
                    cand_weights.append(max(0.0, w))
                elif isinstance(entry, str):
                    candidates.append(entry)
                    cand_weights.append(1.0)
        # Choose a mutation only if any candidate remains after filtering
        if candidates:
            total_w = sum(cand_weights)
            if total_w > 0:
                mut_name = random.choices(candidates, weights=cand_weights, k=1)[0]
            else:
                mut_name = random.choice(candidates)
            spun = mut_name
            spun_name = mut_name
            mutated = True
    if mutated:
        await add_mutated(spun, user_id)
    elif ":" in spun:
        await add_mutated(spun, user_id)
    else:
        await add_to_inventory(spun, user_id)
    await add_xp(1, user_id)
    result = None
    try:
        base_w = things[spun].get("rarity", 0)
        if base_w and base_w > 0:
            base_total = sum(weights) or 0
            base_p = (base_w / base_total) if base_total > 0 else 0
            base_1in = round(1 / base_p) if base_p > 0 else 0
            result = f"You got a **{spun_name}** (*1 in {base_1in:,}*)"
        else:
            result = f"You got a **{spun_name}** (*Evolution*)!"
    except Exception:
        result = f"You got a **{spun_name}** (*Mutation*)!"
    try:
        item_meta = things.get(spun, {})
        item_event = item_meta.get("event")
        if item_event and item_event == active_event:
            msg = event_messages.get(item_event)
            if msg:
                result += msg
    except Exception:
        pass

    return result


async def items_autocomplete(interaction: discord.Interaction, current: str):
    choices = []
    q = current.lower()
    for name in things.keys():
        if q in name.lower():
            choices.append(app_commands.Choice(name=name, value=name))
    if not choices and q == "":
        for name in list(things.keys())[:25]:
            choices.append(app_commands.Choice(name=name, value=name))
    return choices[:25]


async def potions_autocomplete(interaction: discord.Interaction, current: str):
    choices = []
    q = current.lower()
    for name in potions_list.keys():
        if q in name.lower():
            choices.append(app_commands.Choice(name=name, value=name))
    if not choices and q == "":
        for name in list(potions_list.keys())[:25]:
            choices.append(app_commands.Choice(name=name, value=name))
    return choices[:25]


async def events_autocomplete(interaction: discord.Interaction, current: str):
    events = sorted({v.get("event") for v in things.values() if v.get("event")})
    choices = []
    q = current.lower()
    for name in events:
        if q in name.lower():
            choices.append(app_commands.Choice(name=name, value=name))
    if not choices and q == "":
        for name in events[:25]:
            choices.append(app_commands.Choice(name=name, value=name))
    return choices[:25]

@roll_group.command(name="use_potion", description="Use a potion to increase your chances")
async def use_potion(interaction: discord.Interaction, potion: str, amount: int=1):
    potion_functions = {
        "Multi-Spin 1": lambda user_id: potioneffects.msi(spin, user_id),
        "Transmutate 1": lambda user_id: potioneffects.transmutate1(spin, user_id),
        "Transmutate 2": lambda user_id: potioneffects.transmutate2(spin, user_id),
        "Transmutate 3": lambda user_id: potioneffects.transmutate3(spin, user_id),
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
    await interaction.response.defer()
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
        await interaction.followup.send(content="Inventory too large, sent as file instead.", file=file)
    else:
        await interaction.followup.send(embed=embed)

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
    if data["rarity"] > 0 and data["rarity"] != None:
        temp = f"1 in {{:,}}".format(round((totalsum / data['rarity'])))
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
    if data.get("mutations", None) != None:
        # Render mutations and show event-gating when present
        if isinstance(data["mutations"], dict):
            mutation_list = []
            for key, value in data["mutations"].items():
                if isinstance(value, dict) and value.get("event"):
                    mutation_list.append(f"{key} (Event: {value['event']})")
                else:
                    mutation_list.append(f"{key}")
            embed.add_field(name="Mutations", value="\n".join(mutation_list), inline=False)
        elif isinstance(data["mutations"], list):
            mutation_list = []
            for mutation in data["mutations"]:
                if isinstance(mutation, dict):
                    name = mutation.get("name")
                    if not name:
                        continue
                    if mutation.get("event"):
                        mutation_list.append(f"{name} (Event: {mutation['event']})")
                    else:
                        mutation_list.append(name)
                elif isinstance(mutation, str):
                    mutation_list.append(mutation)
            if mutation_list:
                embed.add_field(name="Mutations", value="\n".join(mutation_list), inline=False)
    if data.get("description", None) != None:
        embed.add_field(name="Description", value=data["description"], inline=False)
    await interaction.response.defer(thinking=True)
    await interaction.followup.send(embed=embed)

@roll_group.command(name="rarity_list", description="Show the rarity list")
async def rarity_list(interaction: discord.Interaction):
    await interaction.response.defer()
    temp = ""
    sorted_things = dict(sorted(things.items(), key=lambda item: item[1]["rarity"], reverse=True))
    for i in sorted_things:
        if sorted_things[i]["rarity"] > 0 and sorted_things[i]["rarity"] != None:
            temp += f"**{i}** - 1 in {'{:,}'.format(round((totalsum / sorted_things[i]['rarity'])))}\n"
    await interaction.followup.send(f"**Naturally Spawning Items Rarity List:**\n{temp}")

'''
@roll_group.command(name="values", description="Check the values of items")
async def values(interaction: discord.Interaction):
    await interaction.response.defer()
    temp = ""
    for i in things:
        temp += f"**{i}**: {things[i]['worth']} coins\n"
    await interaction.followup.send(f"**Item Values:**\n{temp}")
'''

async def calculate_rarities():
    global totalsum, roundTo
    for i in things:
        totalsum += things[i]["rarity"]
        if len(str(things[i]["rarity"]))-2 > roundTo:
            roundTo = len(str(things[i]["rarity"]))-2
    totalsum = round(totalsum, roundTo)

evolve.autocomplete('item')(items_autocomplete)
item_info.autocomplete('item')(items_autocomplete)
use_potion.autocomplete('potion')(potions_autocomplete)