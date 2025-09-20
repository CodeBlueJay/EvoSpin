import discord, json
from discord import app_commands
from discord.ext import commands

from database import *

with open("configuration/items.json", "r") as items:
    things = json.load(items)
with open("configuration/shop.json", "r") as shop_file:
    shop_items = json.load(shop_file)

shop_group = discord.app_commands.Group(name="shop", description="Shop commands")

@shop_group.command(name="view", description="View items in the shop")
async def view_items(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Shop Items",
        description="Here is the shop:",
        color=discord.Color.green()
    )
    for key, value in shop_items.items():
        embed.add_field(name=f"**{key}** - *{value['price']}* coins", value=value["description"], inline=False)
    await interaction.response.send_message(embed=embed)