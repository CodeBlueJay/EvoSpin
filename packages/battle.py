import discord, json, random, asyncio, time
from discord import app_commands
from discord.ext import commands

with open("configuration/items.json", "r", encoding="utf-8") as f:
    ITEMS = json.load(f)
with open("configuration/crafting.json", "r", encoding="utf-8") as f:
    CRAFT = json.load(f)

# Simple in-memory battle store: keyed by channel id
battles = {}


class Ability:
    def __init__(self, meta: dict):
        self.id = meta.get("id") or meta.get("name")
        self.name = meta.get("name", self.id)
        self.type = meta.get("type", "damage")
        self.power = float(meta.get("power", 0))
        self.value = float(meta.get("value", meta.get("power", 0)))
        self.target = meta.get("target", "enemy")
        self.cooldown = int(meta.get("cooldown", 5))
        self.duration = int(meta.get("duration", 0))
        self.proc_chance = float(meta.get("proc_chance", 1.0))
        self.description = meta.get("description", "")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "power": self.power,
            "target": self.target,
            "cooldown": self.cooldown,
            "duration": self.duration,
            "proc_chance": self.proc_chance,
            "description": self.description,
        }


class Combatant:
    def __init__(self, user: discord.User, hp: int = 100, abilities=None):
        self.user = user
        self.max_hp = int(hp)
        self.hp = int(hp)
        self.shield = 0
        self.abilities = abilities or []
        # cooldowns: ability_id -> unix timestamp when available
        self.cooldowns = {}

    def is_alive(self):
        return self.hp > 0

    def available_abilities(self):
        now = time.time()
        out = []
        for a in self.abilities:
            ready = self.cooldowns.get(a.id, 0) <= now
            out.append((a, ready))
        return out


class Battle:
    def __init__(self, channel: discord.TextChannel, a: Combatant, b: Combatant):
        self.channel = channel
        self.p1 = a
        self.p2 = b
        self.turn = a.user.id  # user id of who has turn
        self.lock = asyncio.Lock()

    def other(self, user_id):
        return self.p2 if self.p1.user.id == user_id else self.p1

    def actor(self, user_id):
        return self.p1 if self.p1.user.id == user_id else self.p2

    async def use_ability(self, user_id, ability_id):
        async with self.lock:
            # enforce turn
            if user_id != self.turn:
                return False, "It's not your turn."

            actor = self.actor(user_id)
            target = self.other(user_id)
            # find ability
            ability = None
            for a in actor.abilities:
                if a.id == ability_id or a.name.lower() == ability_id.lower():
                    ability = a
                    break
            if not ability:
                return False, "Ability not found."
            now = time.time()
            if actor.cooldowns.get(ability.id, 0) > now:
                rem = int(actor.cooldowns[ability.id] - now)
                return False, f"Ability on cooldown for {rem}s"

            # proc chance
            if random.random() > ability.proc_chance:
                actor.cooldowns[ability.id] = now + ability.cooldown
                return True, f"{actor.user.mention} used **{ability.name}**, but it failed to proc!"

            # apply effect
            if ability.type == "damage":
                dmg = int(ability.power)
                # shield absorbs
                if target.shield > 0:
                    absorbed = min(target.shield, dmg)
                    target.shield -= absorbed
                    dmg -= absorbed
                if dmg > 0:
                    target.hp = max(0, target.hp - dmg)
                actor.cooldowns[ability.id] = now + ability.cooldown
                # switch turn to other
                self.turn = target.user.id
                return True, f"{actor.user.mention} used **{ability.name}** dealing **{int(ability.power)}** damage to {target.user.mention}!"
            elif ability.type == "heal":
                amount = int(ability.value)
                actor.hp = min(actor.max_hp, actor.hp + amount)
                actor.cooldowns[ability.id] = now + ability.cooldown
                self.turn = target.user.id
                return True, f"{actor.user.mention} used **{ability.name}** and healed **{amount}** HP!"
            elif ability.type == "shield":
                amount = int(ability.value)
                actor.shield += amount
                actor.cooldowns[ability.id] = now + ability.cooldown
                self.turn = target.user.id
                return True, f"{actor.user.mention} used **{ability.name}** and gained **{amount}** shield!"
            else:
                actor.cooldowns[ability.id] = now + ability.cooldown
                self.turn = target.user.id
                return True, f"{actor.user.mention} used **{ability.name}** (no-op)."


# build ability registry loader: if an item has an 'abilities' array, create Ability objects
def abilities_for_item(name: str):
    meta = None
    if name in ITEMS:
        meta = ITEMS[name]
    elif name in CRAFT:
        meta = CRAFT[name]
    if not meta:
        return []
    ab_list = []
    for a in meta.get("abilities", []):
        try:
            ab_list.append(Ability(a))
        except Exception:
            continue
    return ab_list


# Command group
battle_group = discord.app_commands.Group(name="battle", description="Battle commands")


@battle_group.command(name="start", description="Start a battle with another user using an item")
async def battle_start(interaction: discord.Interaction, opponent: discord.User, item: str=None, opponent_item: str=None):
    await interaction.response.defer()
    channel = interaction.channel
    if channel.id in battles:
        await interaction.followup.send("A battle is already active in this channel.")
        return

    # validate items
    my_item = (item or "Basic Ball").title()
    opp_item = (opponent_item or "Basic Ball").title()
    if my_item not in ITEMS and my_item not in CRAFT:
        await interaction.followup.send("Your chosen item is not valid.")
        return
    if opp_item not in ITEMS and opp_item not in CRAFT:
        await interaction.followup.send("Opponent's chosen item is not valid.")
        return

    my_abilities = abilities_for_item(my_item)
    opp_abilities = abilities_for_item(opp_item)

    # base HP: try to read 'health' field, else derive from worth
    def base_hp_for(name):
        meta = ITEMS.get(name) or CRAFT.get(name)
        if not meta:
            return 100
        if meta.get("health"):
            return int(meta.get("health"))
        # derive simple HP from worth (clamped)
        w = int(meta.get("worth", 50) or 50)
        return max(50, min(1000, w))

    p1 = Combatant(interaction.user, hp=base_hp_for(my_item), abilities=my_abilities)
    p2 = Combatant(opponent, hp=base_hp_for(opp_item), abilities=opp_abilities)
    battle = Battle(channel, p1, p2)
    battles[channel.id] = battle

    # interactive embed with ability buttons for the challenger
    embed = discord.Embed(title="Battle Started!", description=f"{p1.user.mention} vs {p2.user.mention}", color=discord.Color.red())
    embed.add_field(name=f"{p1.user.name}", value=f"HP: {p1.hp}/{p1.max_hp}\nShield: {p1.shield}", inline=True)
    embed.add_field(name=f"{p2.user.name}", value=f"HP: {p2.hp}/{p2.max_hp}\nShield: {p2.shield}", inline=True)

    view = BattleView(battle)
    await interaction.followup.send(embed=embed, view=view)


class BattleView(discord.ui.View):
    def __init__(self, battle: Battle):
        super().__init__(timeout=None)
        self.battle = battle
        # build buttons dynamically based on abilities and current state
        self._build_buttons()

    def _find_ability(self, owner_id, ability_id):
        owner = self.battle.p1 if self.battle.p1.user.id == owner_id else self.battle.p2
        for a in owner.abilities:
            if a.id == ability_id:
                return a
        return None

    def _ability_label(self, ability: Ability, owner_id: int):
        now = time.time()
        owner = self.battle.p1 if self.battle.p1.user.id == owner_id else self.battle.p2
        cd = int(max(0, owner.cooldowns.get(ability.id, 0) - now))
        if self.battle.turn == owner_id:
            if cd > 0:
                return f"{ability.name} (CD {cd}s)"
            return f"{ability.name}"
        else:
            # show cd or indicate disabled
            if cd > 0:
                return f"{ability.name} (CD {cd}s)"
            return f"{ability.name}"

    def _build_buttons(self):
        # remove existing children if any
        for child in list(self.children):
            try:
                self.remove_item(child)
            except Exception:
                pass

        # helper to add ability button
        def add_for(owner, style):
            for a, _ in owner.available_abilities():
                b = discord.ui.Button(label=self._ability_label(a, owner.user.id), style=style)
                # attach meta for update and callback
                b._owner_id = owner.user.id
                b._ability_id = a.id
                b._ability_name = a.name
                b.callback = self._make_cb(owner.user.id, a.id)
                self.add_item(b)

        add_for(self.battle.p1, discord.ButtonStyle.primary)
        add_for(self.battle.p2, discord.ButtonStyle.secondary)
        # ensure initial enabled/disabled states reflect turn/cds
        self.update_children()

    def update_children(self):
        now = time.time()
        for child in self.children:
            owner_id = getattr(child, "_owner_id", None)
            ability_id = getattr(child, "_ability_id", None)
            if owner_id is None or ability_id is None:
                continue
            ability = self._find_ability(owner_id, ability_id)
            owner = self.battle.p1 if self.battle.p1.user.id == owner_id else self.battle.p2
            cd = int(max(0, owner.cooldowns.get(ability.id, 0) - now))
            # owner may act only on their turn
            if self.battle.turn == owner_id and cd == 0:
                child.disabled = False
            else:
                child.disabled = True
            # update label to show cooldown
            if cd > 0:
                child.label = f"{ability.name} (CD {cd}s)"
            else:
                child.label = f"{ability.name}"

    def _make_cb(self, battle, user_id, ability_id):
        async def cb(interaction: discord.Interaction):
            # only owner can press their ability
            if interaction.user.id != user_id:
                await interaction.response.send_message("You are not the controller for this ability.", ephemeral=True)
                return

            # attempt to use ability
            ok, msg = await battle.use_ability(user_id, ability_id)

            # rebuild/update buttons to reflect new cooldowns/turn
            try:
                self._build_buttons()
            except Exception:
                pass

            # update embed
            e = discord.Embed(title="Battle Update", color=discord.Color.orange())
            e.add_field(name=f"{battle.p1.user.name}", value=f"HP: {battle.p1.hp}/{battle.p1.max_hp}\nShield: {battle.p1.shield}", inline=True)
            e.add_field(name=f"{battle.p2.user.name}", value=f"HP: {battle.p2.hp}/{battle.p2.max_hp}\nShield: {battle.p2.shield}", inline=True)
            e.set_footer(text=msg)

            if not battle.p1.is_alive() or not battle.p2.is_alive():
                winner = battle.p1 if battle.p1.is_alive() else battle.p2
                e.title = f"Battle ended — {winner.user.name} wins!"
                # remove battle
                try:
                    del battles[battle.channel.id]
                except KeyError:
                    pass
                # disable view
                for child in self.children:
                    child.disabled = True
                await interaction.response.edit_message(embed=e, view=self)
                return

            await interaction.response.edit_message(embed=e, view=self)

        return cb


@battle_group.command(name="status", description="Show the current battle status in this channel")
async def battle_status(interaction: discord.Interaction):
    battle = battles.get(interaction.channel.id)
    if not battle:
        await interaction.response.send_message("No active battle in this channel.")
        return
    e = discord.Embed(title="Battle Status", color=discord.Color.green())
    e.add_field(name=f"{battle.p1.user.name}", value=f"HP: {battle.p1.hp}/{battle.p1.max_hp}\nShield: {battle.p1.shield}", inline=True)
    e.add_field(name=f"{battle.p2.user.name}", value=f"HP: {battle.p2.hp}/{battle.p2.max_hp}\nShield: {battle.p2.shield}", inline=True)
    await interaction.response.send_message(embed=e)


@battle_group.command(name="info", description="Show information on all abilities available in the game")
async def battle_info(interaction: discord.Interaction, ability: str=None):
    # gather all abilities from items and craftables
    all_abilities = {}
    for name, meta in ITEMS.items():
        for a in meta.get("abilities", []):
            aid = a.get("id") or a.get("name")
            all_abilities[aid] = a
    for name, meta in CRAFT.items():
        for a in meta.get("abilities", []):
            aid = a.get("id") or a.get("name")
            all_abilities[aid] = a

    if ability:
        key = ability
        a = all_abilities.get(key)
        if not a:
            # try case-insensitive name match
            for v in all_abilities.values():
                if v.get("name","" ).lower() == key.lower():
                    a = v
                    break
        if not a:
            await interaction.response.send_message("Ability not found.")
            return
        e = discord.Embed(title=f"Ability — {a.get('name')}", color=discord.Color.blue())
        e.add_field(name="Type", value=a.get("type", "?"), inline=True)
        e.add_field(name="Power/Value", value=str(a.get("power", a.get('value', ''))), inline=True)
        e.add_field(name="Target", value=a.get("target","enemy"), inline=True)
        e.add_field(name="Cooldown", value=str(a.get("cooldown", 0)) + "s", inline=True)
        e.add_field(name="Duration", value=str(a.get("duration", 0)) + "s", inline=True)
        e.add_field(name="Description", value=a.get("description", "(none)"), inline=False)
        await interaction.response.send_message(embed=e)
        return

    # list summary
    e = discord.Embed(title="All Abilities", color=discord.Color.blue())
    lines = []
    for aid, a in sorted(all_abilities.items()):
        lines.append(f"**{a.get('name')}** — `{aid}` — {a.get('type','')}`")
        if len(lines) >= 25:
            break
    e.description = "\n".join(lines) or "No abilities defined."
    await interaction.response.send_message(embed=e)


# expose for import
__all__ = ["battle_group", "battles"]
