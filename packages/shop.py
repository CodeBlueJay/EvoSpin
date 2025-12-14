import discord, json
from discord import app_commands
from discord.ext import commands

from database import *

with open("configuration/items.json", "r") as items:
    things = json.load(items)
with open("configuration/shop.json", "r") as shop_file:
    shop_items = json.load(shop_file)
with open("configuration/crafting.json", "r") as config_file:
    crafting_items = json.load(config_file)

shop_group = discord.app_commands.Group(name="shop", description="Shop commands")

# Flag toggled by admin commands to expose special event='Shop' items
special_shop_active = False
# Task reference so we can cancel scheduled end when deactivating early
special_shop_task = None

@shop_group.command(name="view", description="View items in the shop")
async def view_items(interaction: discord.Interaction):
    main = discord.Embed(
        title="Shop Items",
        description=f"Balance: `{await get_coins(interaction.user.id)}` coins",
        color=discord.Color.green()
    )
    for key, value in shop_items.items():
        if value.get("hidden"):
            continue
        main.add_field(name=f"**`{key}`** - `{value['price']}` coins", value=value["description"], inline=False)
    await interaction.response.send_message(embed=main)

    # Send special shop as a separate embed if active
    if special_shop_active:
        special_items = [(n, v) for n, v in things.items() if v.get("event") == "Shop"]
        special = discord.Embed(
            title="Special Shop — Limited Stock",
            description="Exclusive items available only while the Special Shop is active.",
            color=discord.Color.gold()
        )
        if special_items:
            for name, meta in special_items:
                price = meta.get("worth", 0)
                desc = meta.get("description", "No description.")
                special.add_field(name=f"**`{name}`** — `{price}` coins", value=desc, inline=False)
        else:
            special.description = "(No special items defined)"
        await interaction.followup.send(embed=special)
    else:
        hint = discord.Embed(title="Special Shop", description="Inactive. An admin can open it with /admin activate_shop", color=discord.Color.dark_gray())
        await interaction.followup.send(embed=hint)

@shop_group.command(name="buy", description="Buy an item from the shop")
async def buy_item(interaction: discord.Interaction, item: str, amount: int=1):
    item = item.title()
    # Normal shop.json purchase (potions)
    if item in shop_items:
        if shop_items[item].get("hidden"):
            await interaction.response.send_message("Item is not available for purchase.")
            return
        user_coins = await get_coins(interaction.user.id)
        item_price = shop_items[item]["price"] * amount
        if user_coins < item_price:
            await interaction.response.send_message(f"You do not have enough coins to buy **{item}**!")
            return
        await remove_coins(item_price, interaction.user.id)
        for i in range(amount):
            await add_potion(item, interaction.user.id)
        await interaction.response.send_message(f"You bought **{amount} {item}** for `{item_price}` coins!")
        return
    # Special shop purchase (event='Shop')
    if special_shop_active and item in things and things[item].get("event") == "Shop":
        price_each = things[item].get("worth", 0)
        total_price = price_each * amount
        user_coins = await get_coins(interaction.user.id)
        if user_coins < total_price:
            await interaction.response.send_message(f"You do not have enough coins to buy **{item}**!")
            return
        await remove_coins(total_price, interaction.user.id)
        for _ in range(amount):
            await add_to_inventory(item, interaction.user.id)
        await interaction.response.send_message(f"You bought **{amount} {item}** (Special) for `{total_price}` coins!")
        return
    await interaction.response.send_message("Item is not in the shop (or special shop inactive)")

@shop_group.command(name="sell", description="Sell an item from your inventory")
async def sell_item(interaction: discord.Interaction, item: str, amount: int=1):
    item = item.title()
    base = things
    if item in things:
        pass
    elif item in crafting_items:
        base = crafting_items
    else:
        await interaction.response.send_message(f"Item does not exist")
        return
    user_inven = await decrypt_inventory(await get_inventory(interaction.user.id))
    crafting_inven = await decrypt_inventory(await get_craftables(interaction.user.id))
    if base == things:
        if int(user_inven.get(item, 0)) < amount:
            await interaction.response.send_message(f"You do not have enough **{item}** to sell!")
            return
    elif base == crafting_items:
        if int(crafting_inven.get(item, 0)) < amount:
            await interaction.response.send_message(f"You do not have enough **{item}** to sell!")
            return
    item_worth = base[item]["worth"]
    total_worth = item_worth * amount
    await add_coins(total_worth, interaction.user.id)
    await add_xp(total_worth, interaction.user.id)
    for i in range(amount):
        if base == things:
            await remove_from_inventory(item, interaction.user.id)
        elif base == crafting_items:
            await remove_craftable(item, interaction.user.id)
    await interaction.response.send_message(f"You sold **{amount} {item}** for **`{total_worth}`** coins!")