import discord, json, random, math
from discord import app_commands
from discord.ext import commands
from database import *
from database import get_pity, inc_pity, set_pity
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


class InventoryPaginator(discord.ui.View):
    def __init__(self, pages: list[discord.Embed], user_id: int):
        super().__init__(timeout=120)
        self.pages = pages
        self.index = 0
        self.user_id = user_id
        # add buttons
        self.prev_button = discord.ui.Button(label="Prev", style=discord.ButtonStyle.secondary)
        self.next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.primary)
        self.prev_button.callback = self.on_prev
        self.next_button.callback = self.on_next
        self.add_item(self.prev_button)
        self.add_item(self.next_button)
        self._update_buttons()

    def _update_buttons(self):
        self.prev_button.disabled = (self.index <= 0)
        self.next_button.disabled = (self.index >= len(self.pages) - 1)

    async def on_prev(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Only the command invoker can navigate this view.", ephemeral=True)
            return
        if self.index > 0:
            self.index -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    async def on_next(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Only the command invoker can navigate this view.", ephemeral=True)
            return
        if self.index < len(self.pages) - 1:
            self.index += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

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

    # ---------------- Pity meter logic ----------------
    # Define rare cutoff as base rarity < 1 (treat ultra-small fractional rarities as rare)
    RARE_CUTOFF = 1
    PITY_THRESHOLD = 50  # guarantee rare after 50 non-rare spins
    pity = await get_pity(user_id)
    # Build list of indices of rare items
    rare_indices = [i for i, w in enumerate(weights) if w < RARE_CUTOFF and w > 0]
    force_rare = pity >= PITY_THRESHOLD and rare_indices
    if force_rare:
        # pick uniformly among rare items (could weight by transformed rarity optionally)
        choice_index = random.choice(rare_indices)
        spun = population[choice_index]
    else:
        spun = random.choices(population, weights=transformed_weights, k=1)[0]

    # Determine if spun item is rare for pity tracking
    try:
        base_rarity = things[spun].get("rarity", 0)
        is_rare = base_rarity > 0 and base_rarity < RARE_CUTOFF
    except Exception:
        is_rare = False
    if force_rare or is_rare:
        await set_pity(user_id, 0)
    else:
        await inc_pity(user_id, 1)
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
    mutation_event_applied = None  # Track if the chosen mutation is event-gated
    mutations = things.get(spun, {}).get("mutations")
    if mutations and random.randint(1, 100) <= mutation_chance:
        candidates = []
        cand_weights = []
        cand_events = []  # parallel list storing event name (or None) for each candidate
        if isinstance(mutations, dict):
            for name, spec in mutations.items():
                if isinstance(spec, dict):
                    mut_event = spec.get("event")
                    if mut_event and mut_event != active_event:
                        continue
                    w = float(spec.get("weight", 1))
                    candidates.append(name)
                    cand_weights.append(max(0.0, w))
                    cand_events.append(mut_event)
                else:
                    w = 1.0
                    candidates.append(name)
                    cand_weights.append(max(0.0, w))
                    cand_events.append(None)
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
                    cand_events.append(mut_event)
                elif isinstance(entry, str):
                    candidates.append(entry)
                    cand_weights.append(1.0)
                    cand_events.append(None)
        if candidates:
            total_w = sum(cand_weights)
            if total_w > 0:
                chosen_index = random.choices(range(len(candidates)), weights=cand_weights, k=1)[0]
            else:
                chosen_index = random.randrange(len(candidates))
            mut_name = candidates[chosen_index]
            spun = mut_name
            spun_name = mut_name
            mutated = True
            mutation_event_applied = cand_events[chosen_index]
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
            pity_display = f" | Pity {await get_pity(user_id)}/{PITY_THRESHOLD}" if base_w >= RARE_CUTOFF else f" | Pity reset"
            result = f"You got a **{spun_name}** (*1 in {base_1in:,}*){pity_display}"
        else:
            result = f"You got a **{spun_name}** (*Evolution*)!"
    except Exception:
        result = f"You got a **{spun_name}** (*Mutation*)!"
    try:
        item_meta = things.get(spun, {})
        item_event = item_meta.get("event")
        # Prefer the item's own event tag, otherwise fall back to the mutation's event gate
        announce_event = item_event if item_event else mutation_event_applied
        if announce_event and announce_event == active_event:
            msg = event_messages.get(announce_event)
            if msg and msg not in result:
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

@roll_group.command(name="inventory", description="Show your inventory (paginated)")
async def inventory(interaction: discord.Interaction, user: discord.User=None, filter: str=None):
    await interaction.response.defer()
    user_obj = user or interaction.user
    self_view = (user is None)
    user_inven = await decrypt_inventory(await get_inventory(user_obj.id))
    potion_inven = await decrypt_inventory(await get_potions(user_obj.id))
    craftables = await decrypt_inventory(await get_craftables(user_obj.id))
    xp_val = await get_xp(user_obj.id)
    number_of_comp = sum(1 for k,v in things.items() if v.get("comp"))
    rare_items_all = [k for k,v in things.items() if v.get('rarity',0) > 0 and v.get('rarity',0) < 1 and v.get('comp')]
    rare_owned = [r for r in rare_items_all if r in user_inven]
    evolvable_now = [k for k,v in things.items() if v.get('next_evo') and k in user_inven and int(user_inven.get(k,0)) >= int(v.get('required',0))]
    event_owned = [k for k in user_inven if things.get(k,{}).get('event')]
    missing_items = [k for k,v in things.items() if v.get('comp') and k not in user_inven]

    # Build evolution chains (respect filter when displaying chains page)
    temp_things = things.copy()
    evolution_chains = []
    for key,data in temp_things.items():
        if data.get('comp'):
            if data.get('next_evo') and data.get('prev_evo') is None:
                chain=[]
                cur=data
                while cur.get('next_evo'):
                    chain.append(cur['name'])
                    cur=temp_things[cur['next_evo']]
                chain.append(cur['name'])
                evolution_chains.append(chain)
            elif data.get('prev_evo') is None:
                evolution_chains.append([data['name']])

    def passes_filter(name: str) -> bool:
        if not filter:
            return True
        f = filter.lower()
        meta = things.get(name, {})
        if f == 'evolvable':
            return meta.get('next_evo') and name in user_inven and int(user_inven.get(name,0)) >= int(meta.get('required',0))
        if f == 'rare':
            r = meta.get('rarity',0)
            return r>0 and r<1
        if f == 'event':
            return meta.get('event') is not None
        if f == 'missing':
            return meta.get('comp') and name not in user_inven
        if f == 'all':
            return True
        return True

    # Page 1: Summary
    summary = discord.Embed(title=f"{user_obj.name}'s Inventory", color=discord.Color.purple())
    summary.set_author(name=user_obj.name, icon_url=user_obj.display_avatar.url)
    summary.description = (
        f"Completion: `{len(user_inven)}/{number_of_comp}` (`{round(len(user_inven)/number_of_comp*100,2)}%`)"\
        f"\nXP: `{xp_val}`"\
        f"\nDistinct Items: `{len(user_inven)}`"\
        f"\nRare Owned: `{len(rare_owned)}/{len(rare_items_all)}`"\
        f"\nEvolvable Now: `{len(evolvable_now)}`"\
        f"\nEvent Items: `{len(event_owned)}`"\
        f"\nMissing Items: `{len(missing_items)}`"\
        f"\nCoins: `{await get_coins(user_obj.id)}`"
    )
    if filter:
        summary.add_field(name="Applied Filter", value=filter, inline=False)

    def chunk_list(values: list[str]) -> list[str]:
        chunks=[]
        current=""
        for v in values:
            line=v
            if len(current)+len(line)+1>1000:
                chunks.append(current)
                current=line
            else:
                current = line if not current else current+"\n"+line
        if current:
            chunks.append(current)
        return chunks or ["(None)"]

    def format_pairs(lst: list[str]) -> list[str]:
        return chunk_list(lst)

    # Page 2: Evolution Chains
    chains_lines=[]
    for chain in evolution_chains:
        filtered=[n for n in chain if passes_filter(n)]
        if not filtered:
            continue
        line=" > ".join([f"**({user_inven[n]}) {n}**" if n in user_inven else n for n in filtered])
        chains_lines.append(line)
    chains_embed=discord.Embed(title="Evolution Chains", color=discord.Color.purple())
    for idx,chunk in enumerate(chunk_list(chains_lines)):
        chains_embed.add_field(name=f"Chains {idx+1}", value=chunk, inline=False)

    # Page 3: Evolvable Now
    evo_lines=[f"**({user_inven[i]}) {i}** -> {things[i]['next_evo']} (req {things[i]['required']})" for i in evolvable_now if passes_filter(i)]
    evo_embed=discord.Embed(title="Evolvable Now", color=discord.Color.green())
    for idx,chunk in enumerate(chunk_list(evo_lines)):
        evo_embed.add_field(name=f"Set {idx+1}", value=chunk, inline=False)

    # Page 4: Rare Owned
    rare_lines=[f"**({user_inven[r]}) {r}**" for r in rare_owned if passes_filter(r)]
    rare_embed=discord.Embed(title="Rare Items", color=discord.Color.gold())
    for idx,chunk in enumerate(chunk_list(rare_lines)):
        rare_embed.add_field(name=f"Group {idx+1}", value=chunk, inline=False)

    # Page 5: Event Items
    event_lines=[f"**({user_inven[e]}) {e}**" for e in event_owned if passes_filter(e)]
    event_embed=discord.Embed(title="Event Items", color=discord.Color.blue())
    for idx,chunk in enumerate(chunk_list(event_lines)):
        event_embed.add_field(name=f"Batch {idx+1}", value=chunk, inline=False)

    # Page 6: Missing Items
    missing_lines=[m for m in missing_items if passes_filter(m)]
    missing_embed=discord.Embed(title="Missing Items", color=discord.Color.red())
    for idx,chunk in enumerate(chunk_list(missing_lines)):
        missing_embed.add_field(name=f"Block {idx+1}", value=chunk, inline=False)

    # Page 7: Craftables
    craft_lines=[f"**({craftables[k]}) {k}**" for k in craftables]
    craft_embed=discord.Embed(title="Craftables", color=discord.Color.teal())
    for idx,chunk in enumerate(chunk_list(craft_lines)):
        craft_embed.add_field(name=f"Craft Set {idx+1}", value=chunk, inline=False)

    # Page 8: Potions
    potion_lines=[f"**({potion_inven[k]}) {k}**" for k in potion_inven]
    potion_embed=discord.Embed(title="Potions", color=discord.Color.magenta())
    for idx,chunk in enumerate(chunk_list(potion_lines)):
        potion_embed.add_field(name=f"Potions {idx+1}", value=chunk, inline=False)

    pages=[summary, chains_embed, evo_embed, rare_embed, event_embed, missing_embed, craft_embed, potion_embed]
    view=InventoryPaginator(pages, interaction.user.id)
    await interaction.followup.send(embed=pages[0], view=view)

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

@roll_group.command(name="pity", description="Show your pity meter status")
async def pity_status(interaction: discord.Interaction, user: discord.User=None):
    uid = user.id if user else interaction.user.id
    current = await get_pity(uid)
    PITY_THRESHOLD = 50
    embed = discord.Embed(title="Pity Meter", color=discord.Color.gold())
    embed.add_field(name="User", value=(user.mention if user else interaction.user.mention), inline=True)
    embed.add_field(name="Progress", value=f"{current}/{PITY_THRESHOLD}", inline=True)
    embed.add_field(name="Counts as rare", value="Natural items with base rarity < 1", inline=False)
    await interaction.response.send_message(embed=embed)

@roll_group.command(name="achievements", description="Show your achievements and quest progress")
async def achievements_cmd(interaction: discord.Interaction, user: discord.User=None):
    uid = user.id if user else interaction.user.id
    inven = await decrypt_inventory(await get_inventory(uid))
    xp = await get_xp(uid)
    unlocked = []
    if xp >= 1:
        unlocked.append("First Spin")
    if len(inven) >= 10:
        unlocked.append("Collector I")
    event_items_owned = [k for k in inven if things.get(k, {}).get('event')]
    if event_items_owned:
        unlocked.append("Event Explorer")
    daily_roll_goal = 25
    weekly_roll_goal = 500
    daily_evolve_goal = 3
    weekly_evolve_goal = 25
    daily_mutation_goal = 1
    weekly_event_goal = 5
    evolve_count = 0  # placeholder until tracked
    mutation_count = 0  # placeholder until tracked
    daily_event_items = len(event_items_owned)
    embed = discord.Embed(title="Achievements & Quests", color=discord.Color.blurple())
    if unlocked:
        embed.add_field(name="Achievements Unlocked", value="\n".join([f"✅ {n}" for n in unlocked]), inline=False)
    else:
        embed.add_field(name="Achievements Unlocked", value="(none yet)", inline=False)
    embed.add_field(name="Next Achievement Hints", value="- Reach 10 distinct items for Collector I\n- Obtain any event item for Event Explorer", inline=False)
    daily_lines = [
        f"Roll {xp}/{daily_roll_goal}",
        f"Evolve {evolve_count}/{daily_evolve_goal}",
        f"Get Mutations {mutation_count}/{daily_mutation_goal}",
    ]
    weekly_lines = [
        f"Roll {xp}/{weekly_roll_goal}",
        f"Evolve {evolve_count}/{weekly_evolve_goal}",
        f"Collect Event Items {daily_event_items}/{weekly_event_goal}",
    ]
    embed.add_field(name="Daily Quests", value="\n".join(daily_lines), inline=False)
    embed.add_field(name="Weekly Quests", value="\n".join(weekly_lines), inline=False)
    embed.set_footer(text="Progress preview; evolve/mutation tracking coming soon.")
    await interaction.response.send_message(embed=embed, ephemeral=True)



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

# ---- Autocomplete for inventory filter ----
async def inventory_filter_autocomplete(interaction: discord.Interaction, current: str):
    options = ["evolvable", "rare", "event", "missing", "all"]
    q = current.lower()
    choices = []
    for opt in options:
        if q in opt.lower():
            choices.append(app_commands.Choice(name=opt, value=opt))
    if not choices and q == "":
        for opt in options:
            choices.append(app_commands.Choice(name=opt, value=opt))
    return choices[:25]

inventory.autocomplete('filter')(inventory_filter_autocomplete)