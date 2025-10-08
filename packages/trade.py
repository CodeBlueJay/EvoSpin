import discord, json
from discord.ext import commands
from discord.ui import Button, View
from discord import app_commands
from database import *

with open("configuration/items.json", "r") as f:
    things = json.load(f)

trade_group = discord.app_commands.Group(name="trade", description="Trading commands")

class TradeView(discord.ui.View):
    def __init__(self, user_id, target_id, target_name=None):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.target_id = target_id
        self.target_name = target_name
        self.user_offer = dict[str, int]()
        self.target_offer = dict[str, int]()
        self.user_accepted = False
        self.target_accepted = False

    def update_embed(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Trade",
            description="Use the buttons to add/remove items and accept/cancel the trade",
            color=discord.Color.blue()
        )
        user_confirmed = f"✅" if self.user_accepted else ""
        target_confirmed = f"✅" if self.target_accepted else ""
        if not self.user_offer:
            embed.add_field(name=f"{user_confirmed} {interaction.user.name}'s Offer", value="None", inline=False)
        else:
            embed.add_field(name=f"{user_confirmed} {interaction.user.name}'s Offer", value="\n".join([f"{item}: {amount}" for item, amount in self.user_offer.items()]), inline=False)
        if not self.target_offer:
            embed.add_field(name=f"{target_confirmed} {self.target_name}'s Offer", value="None", inline=False)
        else:
            embed.add_field(name=f"{target_confirmed} {self.target_name}'s Offer", value="\n".join([f"{item}: {amount}" for item, amount in self.target_offer.items()]), inline=False)
        return embed

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if interaction.user.id not in [self.user_id, self.target_id]:
            await interaction.followup.send("This trade is not for you", ephemeral=True)
            return

        if interaction.user.id == self.user_id:
            self.user_accepted = True
            await interaction.message.edit(embed=self.update_embed(interaction), view=self)
        else:
            self.target_accepted = True
            await interaction.message.edit(embed=self.update_embed(interaction), view=self)

        if self.user_accepted and self.target_accepted:
            for item in self.user_offer:
                await remove_from_inventory(item, self.user_id)
                await add_to_inventory(item, self.target_id)
            for item in self.target_offer:
                await remove_from_inventory(item, self.target_id)
                await add_to_inventory(item, self.user_id)

            await interaction.followup.send("Trade completed!")
            for i in self.children:
                i.disabled = True
            await interaction.message.edit(embed=self.update_embed(interaction), view=self)
            self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.user_id, self.target_id]:
            await interaction.response.send_message("This trade is not for you", ephemeral=True)
            return

        await interaction.response.send_message("Trade cancelled")
        for i in self.children:
            i.disabled = True
        await interaction.message.edit(view=self)
        self.stop()

    @discord.ui.button(label="Add Item", style=discord.ButtonStyle.blurple)
    async def add_item(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.user_id, self.target_id]:
            await interaction.response.send_message("This trade is not for you", ephemeral=True)
            return

        await interaction.response.send_modal(AddItemModal(self, interaction.user.id))

class AddItemModal(discord.ui.Modal, title="Add Item to Trade"):
    item = discord.ui.TextInput(label="Item Name", placeholder="e.g. Apple", max_length=50)
    amount = discord.ui.TextInput(label="Amount", placeholder="e.g. 1", max_length=10)

    def __init__(self, trade_view: TradeView, user_id):
        super().__init__()
        self.trade_view = trade_view
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        item_name = self.item.value.title()
        amount = int(self.amount.value)

        if amount <= 0:
            await interaction.response.send_message("Amount must be greater than 0", ephemeral=True)
            return

        if item_name not in things:
            await interaction.response.send_message("That item does not exist", ephemeral=True)
            return

        user_inven = await decrypt_inventory(await get_inventory(self.user_id))
        if int(user_inven.get(item_name, 0)) < amount:
            await interaction.response.send_message(f"You do not have enough {item_name}(s) to offer", ephemeral=True)
            return

        if self.user_id == self.trade_view.user_id:
            offer = self.trade_view.user_offer
        else:
            offer = self.trade_view.target_offer

        if item_name in offer:
            offer[item_name] += amount
        else:
            offer[item_name] = amount

        self.trade_view.user_accepted = False
        self.trade_view.target_accepted = False
        await interaction.response.edit_message(embed=self.trade_view.update_embed(interaction), view=self.trade_view)

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

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You cannot cancel this gift", ephemeral=True)
            return

        await interaction.response.send_message("Gift cancelled")
        for i in self.children:
            i.disabled = True
        await interaction.message.edit(view=self)
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

@trade_group.command(name="begin", description="Begin a trade with another user")
async def begin(interaction: discord.Interaction, member: discord.Member):
    user_id = interaction.user.id
    target_id = member.id
    target_name = member.name

    await interaction.response.defer()

    if user_id == target_id:
        await interaction.followup.send("You cannot trade with yourself")
        return

    view = TradeView(user_id, target_id, target_name)

    embed = discord.Embed(
        title="Trade",
        description="Use the buttons to add/remove items and accept/cancel the trade",
        color=discord.Color.blue()
    )
    
    embed = view.update_embed(interaction)

    await interaction.followup.send(f"<@{user_id}> wants to trade with you\n\n<@{target_id}>", view=view, embed=embed)