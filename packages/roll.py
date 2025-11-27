import discord, json, random, math, aiosqlite, io
from discord import app_commands
from discord.ext import commands
from database import *
from database import get_pity, inc_pity, set_pity
import packages.potioneffects as potioneffects
import packages.weatherstate as weatherstate
from datetime import datetime, timezone

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


"""
Removed InventoryPaginator view per request to revert inventory to simpler single-embed output.
"""

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

    RARE_CUTOFF = 1
    PITY_THRESHOLD = 50
    pity = await get_pity(user_id)
    rare_indices = [i for i, w in enumerate(weights) if w < RARE_CUTOFF and w > 0]
    force_rare = pity >= PITY_THRESHOLD and rare_indices
    pity_triggered = False
    if force_rare:
        rare_population = [population[i] for i in rare_indices]
        rare_weights_transformed = [transformed_weights[i] for i in rare_indices]
        if sum(rare_weights_transformed) <= 0:
            rare_weights_transformed = [weights[i] for i in rare_indices]
        spun = random.choices(rare_population, weights=rare_weights_transformed, k=1)[0]
        pity_triggered = True
    else:
        spun = random.choices(population, weights=transformed_weights, k=1)[0]

    try:
        base_rarity = things[spun].get("rarity", 0)
        is_rare = base_rarity > 0 and base_rarity < RARE_CUTOFF
    except Exception:
        is_rare = False
    if pity_triggered:
        await set_pity(user_id, 0)
    else:
        if not is_rare:
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
    mutation_event_applied = None
    mutations = things.get(spun, {}).get("mutations")
    if mutations and random.randint(1, 100) <= mutation_chance:
        candidates = []
        cand_weights = []
        cand_events = []
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
            current_pity = await get_pity(user_id)
            if pity_triggered:
                pity_suffix = f" [{current_pity}/{PITY_THRESHOLD} | Guaranteed Rare]"
            else:
                pity_suffix = f" [{current_pity}/{PITY_THRESHOLD}]"
            result = f"You got a **{spun_name}** (*1 in {base_1in:,}*){pity_suffix}"
        else:
            result = f"You got a **{spun_name}** (*Evolution*)!"
    except Exception:
        current_pity = await get_pity(user_id)
        pity_suffix = (
            f" [{current_pity}/{PITY_THRESHOLD} | Guaranteed Rare]" if pity_triggered
            else f" [{current_pity}/{PITY_THRESHOLD}]"
        )
        result = f"You got a **{spun_name}** (*Mutation*)!{pity_suffix}"
    try:
        item_meta = things.get(spun, {})
        item_event = item_meta.get("event")
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


@roll_group.command(name="next_weather", description="Show the next scheduled weather event and the current active weather (UTC)")
async def next_weather(interaction: discord.Interaction):
    def fmt_delta(td_seconds: int) -> str:
        if td_seconds <= 0:
            return "0s"
        parts = []
        days, rem = divmod(td_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if seconds and not parts:
            parts.append(f"{seconds}s")
        return " ".join(parts)

    try:
        state = weatherstate.get_state()
    except Exception:
        state = {}

    next_time = state.get("next_event_time")
    next_name = state.get("next_event_name")
    current_end = state.get("current_event_end_time")
    current_name = state.get("current_event_name")
    now = datetime.now(timezone.utc)

    embed = discord.Embed(title="Weather Scheduler", color=discord.Color.blue())
    embed.set_footer(text="Times shown in UTC")
    embed.timestamp = now

    if next_time and next_name:
        delta = next_time - now
        secs = int(delta.total_seconds())
        rel = fmt_delta(max(0, secs))
        timestr = next_time.strftime("%Y-%m-%d %H:%M UTC")
        val = f"**{next_name}**\nStarts: `{timestr}`\nStarts in: **{rel}**"
    else:
        val = "No next weather event scheduled."
    embed.add_field(name="Next Scheduled Event", value=val, inline=False)

    if current_name and current_end:
        delta2 = current_end - now
        secs2 = int(delta2.total_seconds())
        rel2 = fmt_delta(max(0, secs2))
        endstr = current_end.strftime("%Y-%m-%d %H:%M UTC")
        cur_val = f"**{current_name}**\nEnds: `{endstr}`\nTime remaining: **{rel2}**"
    elif active_event:
        cur_val = f"**{active_event}** — Active (end time unknown)"
    else:
        cur_val = "No weather event is currently active."
    embed.add_field(name="Current Event", value=cur_val, inline=False)

    await interaction.response.send_message(embed=embed)


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
    viewer = user or interaction.user
    uid = viewer.id
    user_inven = await decrypt_inventory(await get_inventory(uid))
    potion_inven = await decrypt_inventory(await get_potions(uid))
    craftables = await decrypt_inventory(await get_craftables(uid))
    mutated = await decrypt_inventory(await get_mutated(uid))

    number_of_comp = sum(1 for k in things if things[k]["comp"])
    completion_pct = round((len(user_inven) / number_of_comp * 100), 2) if number_of_comp else 0

    def build_evolution_lines():
        temp_things = things.copy()
        evolution_chains = []
        for key, data in temp_things.items():
            if not data.get("comp"):
                continue
            if data.get("prev_evo") is None:
                chain = []
                cur = data
                chain.append(cur["name"])
                while cur.get("next_evo") is not None:
                    cur = temp_things[cur["next_evo"]]
                    chain.append(cur["name"])
                evolution_chains.append(chain)
        lines = []
        for chain in evolution_chains:
            parts = []
            for item_name in chain:
                if item_name in user_inven:
                    parts.append(f"**({user_inven[item_name]}) {item_name}**")
                else:
                    parts.append(item_name)
            lines.append(" > ".join(parts))
        return lines

    def chunk_lines(lines, max_chars=1024):
        pages = []
        current = ""
        for line in lines:
            if not current:
                tentative = line
            else:
                tentative = current + "\n" + line
            if len(tentative) > max_chars:
                pages.append(current)
                current = line
            else:
                current = tentative
        if current:
            pages.append(current)
        return pages or ["(Empty)"]

    inventory_pages = chunk_lines(build_evolution_lines())

    class InventoryView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=180)
            self.page = "Overview"
            self.inventory_index = 0
            self.codex_index = 0

        async def render(self, itx: discord.Interaction):
            title = f"{viewer.name}'s Inventory"
            embed = discord.Embed(title=title, color=discord.Color.purple())
            embed.set_author(name=viewer.name, icon_url=viewer.display_avatar.url)
            if self.page == "Overview":
                embed.description = f"Completion: `{len(user_inven)}/{number_of_comp}` (`{completion_pct}%`)\nXP: `{await get_xp(uid)}`"
                embed.add_field(name="Coins", value=f"`{await get_coins(uid)}`", inline=False)
                embed.add_field(name="Counts", value=f"Items: `{len(user_inven)}` | Craftables: `{len(craftables)}` | Potions: `{len(potion_inven)}` | Mutations: `{len(mutated)}`", inline=False)
            elif self.page == "Inventory":
                total = len(inventory_pages)
                content = inventory_pages[self.inventory_index] if total else "(Empty)"
                embed.add_field(name=f"Inventory ({self.inventory_index+1}/{total})", value=content or "(Empty)", inline=False)
            elif self.page == "Craftables":
                craft_lines = [f"**({craftables[k]}) {k}**" for k in craftables]
                for idx, block in enumerate(chunk_lines(craft_lines)):
                    name = "Craftables" if idx == 0 else f"Craftables (cont. {idx+1})"
                    embed.add_field(name=name, value=block or "You have no craftable items!", inline=False)
            elif self.page == "Mutations":
                codex_sections = []
                for base_name, data in things.items():
                    muts = data.get("mutations")
                    if not muts:
                        continue
                    all_mut_names = []
                    if isinstance(muts, dict):
                        all_mut_names.extend(list(muts.keys()))
                    elif isinstance(muts, list):
                        for entry in muts:
                            if isinstance(entry, dict):
                                n = entry.get("name")
                                if n:
                                    all_mut_names.append(n)
                            elif isinstance(entry, str):
                                all_mut_names.append(entry)
                    if not all_mut_names:
                        continue
                    discovered = [m for m in all_mut_names if m in mutated]
                    undiscovered = [m for m in all_mut_names if m not in mutated]
                    section = (
                        f"**{base_name}** — Discovered {len(discovered)}/{len(all_mut_names)}\n"
                        + "Discovered: "
                        + (", ".join(f"`{d}`" for d in discovered) if discovered else "(None)")
                        + "\nUndiscovered: "
                        + (", ".join(f"`{u}`" for u in undiscovered) if undiscovered else "(None)")
                    )
                    codex_sections.append(section)
                codex_sections = codex_sections or ["No mutations exist."]
                codex_pages = chunk_lines(codex_sections)
                if self.codex_index >= len(codex_pages):
                    self.codex_index = 0
                embed.add_field(name=f"Mutations Codex ({self.codex_index+1}/{len(codex_pages)})", value=codex_pages[self.codex_index], inline=False)
            elif self.page == "Potions":
                pot_lines = [f"**({v}) {k}**" for k, v in potion_inven.items()]
                for idx, block in enumerate(chunk_lines(pot_lines)):
                    name = "Potions" if idx == 0 else f"Potions (cont. {idx+1})"
                    embed.add_field(name=name, value=block or "You have no potions!", inline=False)

            for child in self.children:
                if isinstance(child, discord.ui.Button) and child.custom_id in {"prev","next"}:
                    if self.page == "Inventory":
                        child.disabled = not (len(inventory_pages) > 1)
                    elif self.page == "Mutations":
                        # Recompute pages count for enabling navigation
                        test_sections = []
                        for base_name, data in things.items():
                            muts = data.get("mutations")
                            if not muts:
                                continue
                            test_sections.append("x")
                        child.disabled = False  # will be validated in handler
                    else:
                        child.disabled = True
            if not itx.response.is_done():
                await itx.response.edit_message(embed=embed, view=self)
            else:
                await itx.message.edit(embed=embed, view=self)

        @discord.ui.button(label="Overview", style=discord.ButtonStyle.secondary)
        async def btn_overview(self, itx: discord.Interaction, button: discord.ui.Button):
            if itx.user.id != interaction.user.id:
                await itx.response.send_message("Only the command invoker can use these controls.", ephemeral=True)
                return
            self.page = "Overview"
            self.inventory_index = 0
            await self.render(itx)

        @discord.ui.button(label="Inventory", style=discord.ButtonStyle.secondary)
        async def btn_inventory(self, itx: discord.Interaction, button: discord.ui.Button):
            if itx.user.id != interaction.user.id:
                await itx.response.send_message("Only the command invoker can use these controls.", ephemeral=True)
                return
            self.page = "Inventory"
            await self.render(itx)

        @discord.ui.button(label="Craftables", style=discord.ButtonStyle.secondary)
        async def btn_craft(self, itx: discord.Interaction, button: discord.ui.Button):
            if itx.user.id != interaction.user.id:
                await itx.response.send_message("Only the command invoker can use these controls.", ephemeral=True)
                return
            self.page = "Craftables"
            await self.render(itx)

        @discord.ui.button(label="Mutations", style=discord.ButtonStyle.secondary)
        async def btn_mut(self, itx: discord.Interaction, button: discord.ui.Button):
            if itx.user.id != interaction.user.id:
                await itx.response.send_message("Only the command invoker can use these controls.", ephemeral=True)
                return
            self.page = "Mutations"
            self.codex_index = 0
            await self.render(itx)

        @discord.ui.button(label="Potions", style=discord.ButtonStyle.secondary)
        async def btn_pot(self, itx: discord.Interaction, button: discord.ui.Button):
            if itx.user.id != interaction.user.id:
                await itx.response.send_message("Only the command invoker can use these controls.", ephemeral=True)
                return
            self.page = "Potions"
            await self.render(itx)

        @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.primary, custom_id="prev")
        async def btn_prev(self, itx: discord.Interaction, button: discord.ui.Button):
            if itx.user.id != interaction.user.id:
                await itx.response.send_message("Only the command invoker can use these controls.", ephemeral=True)
                return
            if self.page == "Inventory" and len(inventory_pages) > 1:
                self.inventory_index = (self.inventory_index - 1) % len(inventory_pages)
            elif self.page == "Mutations":
                # Rebuild codex pages to navigate
                codex_sections = []
                for base_name, data in things.items():
                    muts = data.get("mutations")
                    if not muts:
                        continue
                    all_mut_names = []
                    if isinstance(muts, dict):
                        all_mut_names.extend(list(muts.keys()))
                    elif isinstance(muts, list):
                        for entry in muts:
                            if isinstance(entry, dict):
                                n = entry.get("name")
                                if n:
                                    all_mut_names.append(n)
                            elif isinstance(entry, str):
                                all_mut_names.append(entry)
                    if not all_mut_names:
                        continue
                    discovered = [m for m in all_mut_names if m in mutated]
                    undiscovered = [m for m in all_mut_names if m not in mutated]
                    section = (
                        f"**{base_name}** — Discovered {len(discovered)}/{len(all_mut_names)}\n"
                        + "Discovered: "
                        + (", ".join(f"`{d}`" for d in discovered) if discovered else "(None)")
                        + "\nUndiscovered: "
                        + (", ".join(f"`{u}`" for u in undiscovered) if undiscovered else "(None)")
                    )
                    codex_sections.append(section)
                codex_sections = codex_sections or ["No mutations exist."]
                codex_pages = chunk_lines(codex_sections)
                if len(codex_pages) > 1:
                    self.codex_index = (self.codex_index - 1) % len(codex_pages)
            await self.render(itx)

        @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.primary, custom_id="next")
        async def btn_next(self, itx: discord.Interaction, button: discord.ui.Button):
            if itx.user.id != interaction.user.id:
                await itx.response.send_message("Only the command invoker can use these controls.", ephemeral=True)
                return
            if self.page == "Inventory" and len(inventory_pages) > 1:
                self.inventory_index = (self.inventory_index + 1) % len(inventory_pages)
            elif self.page == "Mutations":
                codex_sections = []
                for base_name, data in things.items():
                    muts = data.get("mutations")
                    if not muts:
                        continue
                    all_mut_names = []
                    if isinstance(muts, dict):
                        all_mut_names.extend(list(muts.keys()))
                    elif isinstance(muts, list):
                        for entry in muts:
                            if isinstance(entry, dict):
                                n = entry.get("name")
                                if n:
                                    all_mut_names.append(n)
                            elif isinstance(entry, str):
                                all_mut_names.append(entry)
                    if not all_mut_names:
                        continue
                    discovered = [m for m in all_mut_names if m in mutated]
                    undiscovered = [m for m in all_mut_names if m not in mutated]
                    section = (
                        f"**{base_name}** — Discovered {len(discovered)}/{len(all_mut_names)}\n"
                        + "Discovered: "
                        + (", ".join(f"`{d}`" for d in discovered) if discovered else "(None)")
                        + "\nUndiscovered: "
                        + (", ".join(f"`{u}`" for u in undiscovered) if undiscovered else "(None)")
                    )
                    codex_sections.append(section)
                codex_sections = codex_sections or ["No mutations exist."]
                codex_pages = chunk_lines(codex_sections)
                if len(codex_pages) > 1:
                    self.codex_index = (self.codex_index + 1) % len(codex_pages)
            await self.render(itx)

    view = InventoryView()
    init_embed = discord.Embed(title=f"{viewer.name}'s Inventory", color=discord.Color.purple())
    init_embed.set_author(name=viewer.name, icon_url=viewer.display_avatar.url)
    init_embed.description = f"Completion: `{len(user_inven)}/{number_of_comp}` (`{completion_pct}%`)\nXP: `{await get_xp(uid)}`"
    init_embed.add_field(name="Coins", value=f"`{await get_coins(uid)}`", inline=False)
    init_embed.add_field(name="Counts", value=f"Items: `{len(user_inven)}` | Craftables: `{len(craftables)}` | Potions: `{len(potion_inven)}` | Mutations: `{len(mutated)}`", inline=False)
    await interaction.followup.send(embed=init_embed, view=view)

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
    evolve_count = 0
    mutation_count = 0
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

@roll_group.command(name="mutation_codex", description="Show discovered vs undiscovered mutations")
async def mutation_codex(interaction: discord.Interaction, user: discord.User=None):
    await interaction.response.defer()
    viewer = user or interaction.user
    uid = viewer.id
    mutated_owned = await decrypt_inventory(await get_mutated(uid))
    lines = []
    for base_name, data in things.items():
        muts = data.get("mutations")
        if not muts:
            continue
        all_mut_names = []
        if isinstance(muts, dict):
            for k in muts.keys():
                all_mut_names.append(k)
        elif isinstance(muts, list):
            for entry in muts:
                if isinstance(entry, dict):
                    n = entry.get("name")
                    if n:
                        all_mut_names.append(n)
                elif isinstance(entry, str):
                    all_mut_names.append(entry)
        discovered = []
        undiscovered = []
        for m in all_mut_names:
            if m in mutated_owned:
                discovered.append(f"**{m}**")
            else:
                undiscovered.append(m)
        lines.append(f"{base_name}: Discovered {len(discovered)}/{len(all_mut_names)}\n" + ("Discovered: " + (", ".join(discovered) if discovered else "(None)") + "\nUndiscovered: " + (", ".join(undiscovered) if undiscovered else "(None)") ))
    content = "\n\n".join(lines) or "No mutations exist."
    if len(content) > 1900:
        file = discord.File(fp=io.BytesIO(content.encode('utf-8')), filename="mutation_codex.txt")
        await interaction.followup.send(content="Codex too large, sent as file.", file=file)
    else:
        embed = discord.Embed(title=f"Mutation Codex - {viewer.name}", color=discord.Color.dark_gold())
        embed.description = content
        await interaction.followup.send(embed=embed)

@roll_group.command(name="craft_advisor", description="Suggest craftables close to completion")
async def craft_advisor(interaction: discord.Interaction, user: discord.User=None):
    await interaction.response.defer()
    viewer = user or interaction.user
    uid = viewer.id
    inven = await decrypt_inventory(await get_inventory(uid))
    suggestions = []
    for craft_name, cdata in craft.items():
        comps = cdata.get("components", {})
        missing_total = 0
        missing_parts = []
        for comp_name, required_amt in comps.items():
            have = int(inven.get(comp_name, 0))
            if have < required_amt:
                need = required_amt - have
                missing_total += need
                missing_parts.append(f"{need} {comp_name}")
        if missing_total == 0:
            suggestions.append((0, craft_name, "Ready: all components satisfied"))
        else:
            suggestions.append((missing_total, craft_name, "Missing: " + ", ".join(missing_parts)))
    suggestions.sort(key=lambda x: x[0])
    lines = []
    for miss, name, msg in suggestions[:25]:
        lines.append(f"{name}: {msg}")
    body = "\n".join(lines) or "No craftables defined."
    embed = discord.Embed(title=f"Craft Advisor - {viewer.name}", description=body, color=discord.Color.green())
    await interaction.followup.send(embed=embed)

@roll_group.command(name="global_counts", description="Show total counts of every item in existence")
async def global_counts(interaction: discord.Interaction):
    await interaction.response.defer()
    aggregates = {}
    async with aiosqlite.connect(DB_URL) as db:
        cursor = await db.execute("SELECT Inventory, Potions, Craftables, Mutated FROM Users;")
        rows = await cursor.fetchall()
    for inv_str, pot_str, craft_str, mut_str in rows:
        for source, trans in [
            (inv_str, decrypt_inventory),
            (pot_str, decrypt_inventory),
            (craft_str, decrypt_inventory),
            (mut_str, decrypt_inventory),
        ]:
            if source is None or source == "":
                continue
            data = await trans(source)
            for k, v in data.items():
                try:
                    aggregates[k] = aggregates.get(k, 0) + int(v)
                except:
                    pass
    entries = [f"`{name}`: **{aggregates[name]}**" for name in sorted(aggregates.keys())] or ["No items exist."]
    def build_pages(lines, max_chars=1024):
        pages = []
        cur = ""
        for line in lines:
            tentative = line if not cur else cur + "\n" + line
            if len(tentative) > max_chars:
                pages.append(cur)
                cur = line
            else:
                cur = tentative
        if cur:
            pages.append(cur)
        return pages or ["(Empty)"]
    pages = build_pages(entries)
    class CountsView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.index = 0
        async def render(self, itx: discord.Interaction):
            total = len(pages)
            embed = discord.Embed(title="Global Item Counts", color=discord.Color.blue())
            embed.description = f"Page {self.index+1}/{total}\n\n" + pages[self.index]
            if not itx.response.is_done():
                await itx.response.edit_message(embed=embed, view=self)
            else:
                await itx.message.edit(embed=embed, view=self)
        @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.secondary)
        async def prev(self, itx: discord.Interaction, button: discord.ui.Button):
            if itx.user.id != interaction.user.id:
                await itx.response.send_message("Only the command invoker can use these controls.", ephemeral=True)
                return
            if len(pages) > 1:
                self.index = (self.index - 1) % len(pages)
            await self.render(itx)
        @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.secondary)
        async def next(self, itx: discord.Interaction, button: discord.ui.Button):
            if itx.user.id != interaction.user.id:
                await itx.response.send_message("Only the command invoker can use these controls.", ephemeral=True)
                return
            if len(pages) > 1:
                self.index = (self.index + 1) % len(pages)
            await self.render(itx)
    view = CountsView()
    init_embed = discord.Embed(title="Global Item Counts", color=discord.Color.blue())
    init_embed.description = f"Page 1/{len(pages)}\n\n" + pages[0]
    await interaction.followup.send(embed=init_embed, view=view)

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