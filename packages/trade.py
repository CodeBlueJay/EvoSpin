import discord, json
from discord.ext import commands
from discord.ui import Button, View
from discord import app_commands
from database import *

with open("configuration/items.json", "r") as f:
    things = json.load(f)

trade_group = discord.app_commands.Group(name="trade", description="Trading commands")

class GiveView(discord.ui.View):
    def __init__(self, user_id, target_id, item, amount):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.target_id = target_id
        self.item = item
        self.amount = amount

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("This gift is not for you", ephemeral=True)
            return

        for i in range(self.amount):
            await remove_from_inventory(self.item, self.user_id)
            await add_to_inventory(self.item, self.target_id)

        await interaction.response.send_message("Gift accepted! You received **" + str(self.amount) + " " + self.item + "(s)**")
        for i in self.children:
            i.disabled = True
        await interaction.message.edit(view=self)
        self.stop()
    
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("This gift is not for you", ephemeral=True)
            return

        await interaction.response.send_message("Gift declined")
        for i in self.children:
            i.disabled = True
        self.stop()

@trade_group.command(name="give", description="Give an item to another user")
async def give(interaction: discord.Interaction, member: discord.Member, item: str, amount: int=1):
    user_id = interaction.user.id
    target_id = member.id
    item = item.title()
    user_inven = await decrypt_inventory(await get_inventory(user_id))

    if user_id == target_id:
        await interaction.response.send_message("You cannot give yourself items")
        return
    
    if not(item in things):
        await interaction.response.send_message("That item does not exist")
        return
    if int(user_inven[item]) < amount:
        await interaction.response.send_message("You do not have enough " + item + "(s) to give")
        return

    await interaction.response.send_message(f"<@{user_id}> is giving you **{amount} {item}(s)**\n\n<@{target_id}>", view=GiveView(user_id, target_id, item, amount))