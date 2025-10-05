import discord, json, random
from discord import app_commands
from discord.ui import Button, View
from discord.ext import commands

from database import *
from packages.roll import spin

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
    temp = ""
    await interaction.response.send_message(f"Admin: Rolling `{amount}` times")
    for i in range(amount):
        spun = await spin(interaction.user.id, item, potion_strength=potion_strength, transmutate_amount=transmutate_amount, mutation_chance=mutation_chance)
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
    for i in range(amount):
        await add_potion(potion.title(), user.id)
    await interaction.response.send_message(f"Gave **{amount}** **{potion.title()}** to {user.mention}!")

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
    total = sum([things[i]["rarity"] for i in things if things[i]["rarity"] > 0])
    embed.add_field(name="Rarity", value=f"1 in {'{:,}'.format(round((total / things[item.title()]['rarity'])))}")
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