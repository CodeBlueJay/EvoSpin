import discord, json, random, asyncio, math
from discord import app_commands
from discord.ui import Button, View
from discord.ext import commands

from database import *
import packages.roll as roll

with open("configuration/items.json", "r") as items:
    things = json.load(items)
with open("configuration/settings.json", "r") as settings_file:
    settings = json.load(settings_file)
with open("configuration/shop.json", "r") as potions:
    potion_data = json.load(potions)
with open("configuration/crafting.json", "r") as craftables:
    crafting_data = json.load(craftables)

class DropView(discord.ui.View):
    def __init__(self, admin_id, item, amount):
        super().__init__(timeout=None)
        self.admin_id = admin_id
        self.item = item
        self.amount = amount
        self.claimed = False

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.green)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.claimed:
            await interaction.response.send_message("This drop has already been claimed", ephemeral=True)
            return

        for i in range(self.amount):
            await add_to_inventory(self.item, interaction.user.id)

        self.claimed = True
        await interaction.response.send_message(f"{interaction.user.mention} claimed the drop and received **{self.amount}** **{self.item}**!")
        button.disabled = True
        await interaction.message.edit(view=self)
        self.stop()

admin_group = discord.app_commands.Group(name="admin", description="Admin commands")

@admin_group.command(name="roll", description="Admin type command :fire:")
async def roll_amount(interaction: discord.Interaction, amount: int=1, item: str=None, potion_strength: float=0.0, transmutate_amount: int=0, seperate: bool=False, mutation_chance: int=1):
    if interaction.user.id not in settings["admins"]:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    # Defer immediately to avoid Unknown interaction if this takes too long
    await interaction.response.defer(thinking=True)
    temp = ""
    await interaction.followup.send(f"Admin: Rolling `{amount}` times")
    for i in range(amount):
        spun = await roll.spin(interaction.user.id, item, potion_strength=potion_strength, transmutate_amount=transmutate_amount, mutation_chance=mutation_chance)
        temp += spun + "\n"
        if seperate:
            await interaction.followup.send(spun)
            temp = ""
    try:
        if not seperate:
            await interaction.followup.send(temp)
    except:
        await interaction.followup.send("Complete (result too large to show in message)")

@admin_group.command(name="give_item", description="Give an item to a user")
async def give(interaction: discord.Interaction, user: discord.User, item: str, amount: int=1):
    if interaction.user.id not in settings["admins"]:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    for i in range(amount):
        await add_to_inventory(item.title(), user.id)
    await interaction.response.send_message(f"Gave **{amount}** **{item.title()}** to {user.mention}!")

@admin_group.command(name="give_coins", description="Give coins to a user")
async def give_coins(interaction: discord.Interaction, user: discord.User, amount: int):
    if interaction.user.id not in settings["admins"]:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    await add_coins(amount, user.id)
    await interaction.response.send_message(f"Added **{amount}** coins to {user.mention}!")

@admin_group.command(name="reset_db", description="Empty the database")
async def empty_db_cmd(interaction: discord.Interaction):
    if interaction.user.id not in settings["admins"]:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    await empty_db()
    await init_db()
    await interaction.response.send_message("Reset the database!")

@admin_group.command(name="clear_inventory", description="Clear a user's inventory")
async def clear_inventory_cmd(interaction: discord.Interaction, user: discord.User):
    if interaction.user.id not in settings["admins"]:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    await clear_inventory(user.id)
    await interaction.response.send_message(f"Cleared {user.mention}'s inventory!")

@admin_group.command(name="give_potion", description="Give a potion to a user")
async def give_potion(interaction: discord.Interaction, user: discord.User, potion: str, amount: int=1 ):
    if interaction.user.id not in settings["admins"]:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    for i in range(amount):
        await add_potion(potion.title(), user.id)
    await interaction.followup.send(f"Gave **{amount}** **{potion.title()}** to {user.mention}!")

@admin_group.command(name="clear_potions", description="Clear a user's potions")
async def clear_user_potions(interaction: discord.Interaction, user: discord.User):
    if interaction.user.id not in settings["admins"]:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    await clear_potions(user.id)
    await interaction.response.send_message(f"Cleared {user.mention}'s potions!")

@admin_group.command(name="add_xp", description="Add XP to a user")
async def add_xp_cmd(interaction: discord.Interaction, user: discord.User, amount: int):
    if interaction.user.id not in settings["admins"]:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    await add_xp(amount, user.id)
    await interaction.response.send_message(f"Added **{amount}** XP to {user.mention}!")

@admin_group.command(name="remove_xp", description="Remove XP from a user")
async def remove_xp_cmd(interaction: discord.Interaction, user: discord.User, amount: int):
    if interaction.user.id not in settings["admins"]:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    await remove_xp(amount, user.id)
    await interaction.response.send_message(f"Removed **{amount}** XP from {user.mention}!")

@admin_group.command(name="add_column", description="Add a column to the database")
async def add_column_cmd(interaction: discord.Interaction, column_name: str, data_type: str=""):
    if interaction.user.id not in settings["admins"]:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    await add_column(column_name, data_type)
    await interaction.response.send_message(f"Added column **{column_name}** to the database!")

@admin_group.command(name="add_craftable", description="Add a craftable item to a user")
async def add_craftable_cmd(interaction: discord.Interaction, user: discord.User, item: str, amount: int=1):
    if interaction.user.id not in settings["admins"]:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    for i in range(amount):
        await add_craftable(item.title(), user.id)
    await interaction.response.send_message(f"Gave **{amount}** **{item.title()}** to {user.mention}!")

@admin_group.command(name="drop", description="Create a drop giveaway")
async def drop_cmd(interaction: discord.Interaction, item: str, amount: int=1):
    if interaction.user.id not in settings["admins"]:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    if not(item.title() in things):
        await interaction.response.send_message("That item does not exist")
        return
    await interaction.response.send_message(f"Spawned a new drop for **{amount}** **{item.title()}(s)**!")
    embed = discord.Embed(
        title=f"Item Drop!",
        description=f"First person to click the button gets **{amount}** **{item.title()}(s)**!",
        color=discord.Color.gold()
    )
    embed.add_field(name="Item", value=item.title())
    embed.add_field(name="Amount", value=str(amount))
    if things[item.title()]["rarity"] > 0:
        total = sum([things[i]["rarity"] for i in things if things[i]["rarity"] > 0])
        embed.add_field(name="Rarity", value=f"1 in {'{:,}'.format(round((total / things[item.title()]['rarity'])))}")
    else:
        embed.add_field(name="Rarity", value="Evolution")
    embed.add_field(name="Value", value=str(things[item.title()]["worth"]))
    await interaction.followup.send(embed=embed, view=DropView(interaction.user.id, item.title(), amount))

@admin_group.command(name="max", description="Give a user all items, potions, and craftables")
async def max_cmd(interaction: discord.Interaction, user: discord.User):
    if interaction.user.id not in settings["admins"]:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)

    added = 0
    for k, v in things.items():
        if v.get("comp", True):
            await add_to_inventory(k, user.id)
    for potion in potion_data:
        await add_potion(potion, user.id)
    for craftable in crafting_data:
        await add_craftable(craftable, user.id)
    await interaction.followup.send(f"Gave full completion to {user.mention}!")

@admin_group.command(name="check_dupes", description="Check for abbreviation conflicts")
async def check_dupes_cmd(interaction: discord.Interaction):
    if interaction.user.id not in settings["admins"]:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)

    abbevs = {}
    dupe_abbevs = []
    for k, v in things.items():
        if v.get("abbev", None):
            if v["abbev"] in abbevs:
                dupe_abbevs.append(v["abbev"])
            else:
                abbevs[v["abbev"]] = k

    if dupe_abbevs:
        response = "Found the following abbreviation conflicts:\n"
        for dupe in dupe_abbevs:
            items_with_dupe = [k for k, v in things.items() if v.get("abbev", None) == dupe]
            response += f"Abbreviation **{dupe}** is used by: {', '.join(items_with_dupe)}\n"
        await interaction.followup.send(response)
    else:
        await interaction.followup.send("No abbreviation conflicts found.")

@admin_group.command(name="remove_column", description="Remove a column from the database")
async def remove_column_cmd(interaction: discord.Interaction, column_name: str):
    if interaction.user.id not in settings["admins"]:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    await remove_column(column_name)
    await interaction.response.send_message(f"Removed column **{column_name}** from the database!")

@admin_group.command(name="add_mutated", description="Add a mutated item to a user")
async def add_mutated_cmd(interaction: discord.Interaction, user: discord.User, item: str, amount: int=1):
    if interaction.user.id not in settings["admins"]:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    for i in range(amount):
        await add_mutated(item.title(), user.id)
    await interaction.response.send_message(f"Gave **{amount}** **{item.title()}** to {user.mention}!")

@admin_group.command(name="clear_mutated", description="Clear a user's mutated items")
async def clear_mutated_cmd(interaction: discord.Interaction, user: discord.User):
    if interaction.user.id not in settings["admins"]:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    await clear_mutated(user.id)
    await interaction.response.send_message(f"Cleared {user.mention}'s mutated items!")

class FalseButton(discord.ui.Button):
    def __init__(self, y: int):
        super().__init__(label="\u200b", style=discord.ButtonStyle.secondary, row=y)

    async def callback(self, interaction: discord.Interaction):
        self.style = discord.ButtonStyle.danger
        self.disabled = True
        await interaction.response.edit_message(view=self.view)

class CorrectButton(discord.ui.Button):
    def __init__(self, y: int, item: str, amount: int=1):
        super().__init__(label="\u200b", style=discord.ButtonStyle.secondary, row=y)
        self.item = item
        self.amount = amount

    async def callback(self, interaction: discord.Interaction):
        self.style = discord.ButtonStyle.success
        self.disabled = True
        self.view.claimed = True
        await interaction.response.edit_message(view=self.view)
        await interaction.followup.send(f"{interaction.user.mention} pressed the correct button!")
        await add_to_inventory(self.item, interaction.user.id)
        await interaction.followup.send(f"{interaction.user.mention} received **{str(self.amount)} {self.item}**!")
        self.view.stop()

class ItemBoard(discord.ui.View):
    def __init__(self, item, height, width, amount):
        super().__init__(timeout=120)
        self.item = item
        self.claimed = False
        self.height = height
        self.width = width
        self.amount = amount

        correctX = random.randint(0, self.width - 1)
        correctY = random.randint(0, self.height - 1)
        for y in range(self.height):
            for x in range(self.width):
                if (x, y) == (correctX, correctY):
                    self.add_item(CorrectButton(y, self.item, self.amount))
                else:
                    self.add_item(FalseButton(y))

@admin_group.command(name="item_board", description="Press the correct button and get an item")
async def create_item_board(interaction: discord.Interaction, amount: int, item: str, height: int=3, width: int=3):
    item = item.title()
    if interaction.user.id not in settings["admins"]:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    view = ItemBoard(item, height, width, amount)
    await interaction.response.send_message(f"First person to click the correct button gets **{amount} {item}(s)**", view=view)

@admin_group.command(name="lucky_3", description="Toggle the Triple Spin event for 60 seconds")
async def toggle_lucky_3(interaction: discord.Interaction):
    if interaction.user.id not in settings["admins"]:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    roll.lucky3 = True
    await interaction.response.send_message(f"Triple Spin event has started! All rolls are multiplied by 3 for the next 60 seconds! This effect stacks with potions.")
    await asyncio.sleep(60)
    roll.lucky3 = False
    await interaction.followup.send("Triple Spin event has ended.")

@admin_group.command(name="lucky_2x", description="Toggle the 2x Luck event for 60 seconds")
async def toggle_lucky_2x(interaction: discord.Interaction):
    if interaction.user.id not in settings["admins"]:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    roll.lucky2x = True
    await interaction.response.send_message(f"2x Luck event has started! All rolls have double the luck for the next 60 seconds! This effect stacks with potions.")
    await asyncio.sleep(60)
    roll.lucky2x = False
    await interaction.followup.send("2x Luck event has ended.")

@admin_group.command(name="activate_event", description="Activate a special event (e.g. Galaxy, Winter Wonderland)")
async def activate_event(interaction: discord.Interaction, event: str, duration: int=60):
    if interaction.user.id not in settings["admins"]:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    event_name = event.title()
    roll.active_event = event_name
    await interaction.response.send_message(f"{event_name} event has started for {duration} seconds!")
    await asyncio.sleep(duration)
    if roll.active_event == event_name:
        roll.active_event = None
        await interaction.followup.send(f"{event_name} event has ended.")

@admin_group.command(name="deactivate_event", description="Deactivate the currently active event")
async def deactivate_event(interaction: discord.Interaction):
    if interaction.user.id not in settings["admins"]:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    if roll.active_event is None:
        await interaction.response.send_message("No event is currently active.")
        return
    old = roll.active_event
    roll.active_event = None
    await interaction.response.send_message(f"{old} event has been deactivated.")

@admin_group.command(name="list_events", description="List all events detected from items.json (items with an 'event' field)")
async def list_events(interaction: discord.Interaction):
    if interaction.user.id not in settings["admins"]:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    events = set()
    for k, v in things.items():
        ev = v.get("event")
        if ev:
            events.add(ev)
    if not events:
        await interaction.response.send_message("No events are defined in items.json.")
        return
    await interaction.response.send_message("Defined events: " + ", ".join(sorted(events)))

class GroupGiveawayView(discord.ui.View):
    def __init__(self, admin_id, item):
        super().__init__(timeout=60)
        self.admin_id = admin_id
        self.item = item
        self.claimed = False
        self.users = []
        self.message = None

    async def on_timeout(self):
        unique_users = list(set(self.users))
        for i in unique_users:
            await add_to_inventory(self.item, i)
        if self.message:
            for child in self.children:
                child.disabled = True
            await self.message.edit(view=self)
            await self.message.channel.send(f"{str(len(unique_users))} users claimed their **{self.item}**!")

    @discord.ui.button(label="I want one", style=discord.ButtonStyle.green)
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id in self.users:
            await interaction.followup.send("You are already in this giveaway!", ephemeral=True)
            return
        self.users.append(interaction.user.id)
        await interaction.followup.send(f"You have been added to the giveaway for **{self.item}**!", ephemeral=True)

@admin_group.command(name="group_giveaway", description="Give everyone who clicks the button an item")
async def group_giveaway(interaction: discord.Interaction, item: str):
    if interaction.user.id not in settings["admins"]:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return
    if not(item.title() in things):
        await interaction.response.send_message("That item does not exist")
        return
    await interaction.response.send_message(f"Started a group giveaway for **{item.title()}(s)**!")
    embed = discord.Embed(
        title=f"Group Giveaway!",
        description=f"Click the button below to claim **{item.title()}(s)**!\nEnds in 60 seconds!",
        color=discord.Color.purple()
    )
    embed.add_field(name="Item", value=item.title())
    if things[item.title()]["rarity"] > 0:
        total = sum([things[i]["rarity"] for i in things if things[i]["rarity"] > 0])
        embed.add_field(name="Rarity", value=f"1 in {'{:,}'.format(round((total / things[item.title()]['rarity'])))}")
    else:
        embed.add_field(name="Rarity", value="Evolution")
    embed.add_field(name="Value", value=str(things[item.title()]["worth"]))
    view = GroupGiveawayView(interaction.user.id, item.title())
    message = await interaction.followup.send(embed=embed, view=view)
    view.message = message

@admin_group.command(name="preview", description="Preview spawn odds and effects (events, potions, admin events)")
async def preview(interaction: discord.Interaction, event: str=None, potion: str=None, admin_event: str=None, xp: int=None, item: str=None):
    """Combined simulation for spawn odds.

    You may provide any combination of:
    - event: name of a special event to include its items in the population
    - potion: name of a potion to simulate its effect (luck or multispin)
    - admin_event: comma-separated admin flags like "lucky_2x" or "lucky_3"
    - xp: integer XP value to simulate (affects luck via XP progression)
    - item: single item name to get a focused "1 in X" result
    """
    if interaction.user.id not in settings["admins"]:
        await interaction.response.send_message("You are not allowed to use this command!", ephemeral=True)
        return

    def natural_population(include_event_items=True, event_name=None):
        pop = []
        ws = []
        for v in things.values():
            if v.get("rarity", 0) > 0:
                item_event = v.get("event")
                if not item_event:
                    pop.append(v)
                    ws.append(v.get("rarity", 0))
                else:
                    if include_event_items and event_name and item_event == event_name:
                        pop.append(v)
                        ws.append(v.get("rarity", 0))
        return pop, ws

    event_name = event.title() if event else None
    pop, ws = natural_population(include_event_items=bool(event_name), event_name=event_name)
    if not pop:
        await interaction.response.send_message("No spawnable items found for the requested simulation.")
        return

    admin_flags = set()
    if admin_event:
        for part in admin_event.split(','):
            admin_flags.add(part.strip().lower())
    lucky2x_flag = any(k in admin_flags for k in ("lucky_2x", "lucky2x", "2x", "2x_luck"))
    lucky3_flag = any(k in admin_flags for k in ("lucky_3", "lucky3", "3x", "triple"))

    xp_val = xp if xp is not None else 0
    xp_scale = roll.settings.get("xp_scale", 25000)
    max_luck_strength = roll.settings.get("max_luck_strength", 0.8)
    potion_exponent_factor = roll.settings.get("potion_exponent_factor", 0.5)
    progress = 1 - math.exp(-xp_val / xp_scale) if xp_scale > 0 else 0
    luck_strength = progress * max_luck_strength
    exponent_base = 1 - luck_strength

    effective_potion_strength = None
    if potion:
        p_name = potion.title()
        potion_map = {
            "Luck 1": 2.0,
            "Luck 2": 3.0,
            "Luck 3": 5.0,
            "Godly": 50.0,
        }
        effective_potion_strength = potion_map.get(p_name, 1.0)
    else:
        effective_potion_strength = 1.0

    if lucky2x_flag:
        effective_potion_strength = effective_potion_strength * 2.0

    exponent_final = exponent_base * (1 - effective_potion_strength * potion_exponent_factor)
    if exponent_final < 0.1:
        exponent_final = 0.1

    transformed = [w ** exponent_final for w in ws]
    s = sum(transformed) or 1
    probs = [t / s for t in transformed]

    def one_in(p):
        if p <= 0:
            return "∞"
        try:
            val = round(1 / p)
            return f"1 in {val:,}"
        except Exception:
            return "∞"

    if item:
        it_name = item.title()
        match = None
        for idx, v in enumerate(pop):
            if v.get("name") == it_name or v.get("name").lower() == it_name.lower():
                match = (idx, v)
                break
        if not match:
            await interaction.response.send_message(f"Item `{it_name}` not found in simulated population.", ephemeral=True)
            return
        idx, v = match
    if item:
        total_raw = sum(ws) or 1
        base_raw_probs = [w / total_raw for w in ws]
        embed = discord.Embed(title=f"Simulation result: {it_name}", color=discord.Color.green())
        embed.add_field(name="Simulated Odds", value=one_in(probs[idx]), inline=True)
        embed.add_field(name="Base (natural) Odds", value=one_in(base_raw_probs[idx]), inline=True)
        embed.add_field(name="Simulation details", value=f"xp={xp_val}, potion={potion or 'none'}, admin_events={', '.join(admin_flags) or 'none'}, event={event_name or 'none'}", inline=False)
        await interaction.response.send_message(embed=embed)
        return

    indexed = list(enumerate(pop))
    total_raw = sum(ws) or 1
    base_raw_probs = [w / total_raw for w in ws]
    indexed_sorted = sorted(indexed, key=lambda x: probs[x[0]])[:15]
    lines = []
    for idx, it in indexed_sorted:
        lines.append((idx, it))

    embed = discord.Embed(title="Preview Simulation", color=discord.Color.blue())
    details = f"xp={xp_val}, potion={potion or 'none'}, admin_events={', '.join(admin_flags) or 'none'}, event={event_name or 'none'}"
    table = [f"{it.get('name'):<30} | base {one_in(base_raw_probs[idx]):>14} | sim {one_in(probs[idx]):>14}" for idx, it in lines]
    block = "```text\n" + "\n".join(table) + "\n```"
    if len(block) > 1000:
        rows = list(table)
        while rows and len("```text\n" + "\n".join(rows) + "\n```") > 1000:
            rows.pop()
        remaining = len(table) - len(rows)
        if remaining > 0:
            summary = f"... and {remaining} more"
            if len("```text\n" + "\n".join(rows + [summary]) + "\n```") <= 1000:
                rows.append(summary)
            elif rows:
                rows[-1] = summary
        block = "```text\n" + "\n".join(rows) + "\n```"
    embed.add_field(name="Top spawn odds (rarest → common)", value=block, inline=False)
    embed.add_field(name="Simulation details", value=details, inline=False)
    multispin_info = None
    if potion:
        ms_map = {"Multi-Spin 1": 3, "Multi-Spin 2": 5, "Multi-Spin 3": 10}
        if potion.title() in ms_map:
            base_count = ms_map[potion.title()]
            total_spins = base_count * (3 if lucky3_flag else 1)
            multispin_info = f"Multi-spin: base {base_count}, with Lucky3 -> {total_spins} total spins"
    if multispin_info:
        embed.add_field(name="Multi-spin info", value=multispin_info, inline=False)

    await interaction.response.send_message(embed=embed)

roll_amount.autocomplete('item')(roll.items_autocomplete)
give.autocomplete('item')(roll.items_autocomplete)
drop_cmd.autocomplete('item')(roll.items_autocomplete)
group_giveaway.autocomplete('item')(roll.items_autocomplete)
create_item_board.autocomplete('item')(roll.items_autocomplete)
add_mutated_cmd.autocomplete('item')(roll.items_autocomplete)
give_potion.autocomplete('potion')(roll.potions_autocomplete)
activate_event.autocomplete('event')(roll.events_autocomplete)
preview.autocomplete('event')(roll.events_autocomplete)
preview.autocomplete('potion')(roll.potions_autocomplete)
preview.autocomplete('item')(roll.items_autocomplete)
async def admin_events_autocomplete(interaction: discord.Interaction, current: str):
    choices = []
    q = current.lower()
    options = ["Lucky 2x", "Lucky 3"]
    for name in options:
        if q in name.lower():
            choices.append(app_commands.Choice(name=name, value=name))
    if not choices and q == "":
        for name in options:
            choices.append(app_commands.Choice(name=name, value=name))
    return choices[:25]

preview.autocomplete('admin_event')(admin_events_autocomplete)