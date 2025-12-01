import discord, os, asyncio, random, json
from datetime import datetime, timezone, timedelta
import packages.weatherstate as weatherstate
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from database import *

module = {}
for file in os.listdir("packages"):
    if not(file.startswith("_")):
        filename = file[:-3]
        module[filename] = __import__(f"packages.{filename}", fromlist=[filename])

intents = discord.Intents.default()
intents.message_content = True

load_dotenv()
TOKEN = os.getenv("TOKEN")
DEV_TOKEN = os.getenv("DEV_TOKEN")

bot = commands.Bot(command_prefix="!", intents=intents)

cogs = [
    module["roll"].roll_group,
    module["admin"].admin_group,
    module["shop"].shop_group,
    #module["battle"].battle_group,
    module["craft"].craft_group,
    module["trade"].trade_group
]

async def get_user(user_id):
    user = await bot.fetch_user(user_id)
    return user.name


async def weather_scheduler(bot: commands.Bot):
    try:
        with open("configuration/settings.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        print("weather_scheduler: failed to read settings.json")
        return

    min_i = int(cfg.get("weather_event_min_interval_minutes", 30))
    max_i = int(cfg.get("weather_event_max_interval_minutes", 60))
    duration_m = int(cfg.get("weather_event_duration_minutes", 15))
    configured = cfg.get("weather_events", []) or []
    ann_channels = cfg.get("announcement_channel")
    if isinstance(ann_channels, (int, str)):
        ann_channels = [ann_channels]

    def build_event_pool():
        """Return (events, weights).

        We first consult configured events in settings; if provided as a list, use those
        event names and look up weights from `weather_event_weights` mapping in settings.
        If settings do not define weights for an event, fall back to computing a weight
        from the sum of item rarities for items that declare that event in
        `configuration/items.json`. Events named "Shop" are ignored.
        """
        cfg_events = list(configured) if configured else None
        items = {}
        try:
            with open("configuration/items.json", "r", encoding="utf-8") as f:
                items = json.load(f)
        except Exception:
            items = {}
        discovered = sorted({v.get("event") for v in items.values() if v.get("event")})
        discovered = [e for e in discovered if e and e != "Shop"]
        events = cfg_events or discovered
        if not events:
            return ([], [])
        weights_cfg = cfg.get("weather_event_weights", {}) or {}
        weights = []
        for ev in events:
            if ev == "Shop":
                continue
            w = None
            try:
                w = int(weights_cfg.get(ev, None)) if weights_cfg.get(ev, None) is not None else None
            except Exception:
                w = None
            if w is None:
                try:
                    total_rarity = 0
                    for v in items.values():
                        if v.get("event") == ev:
                            r = int(v.get("rarity", 0) or 0)
                            total_rarity += max(1, r)
                    w = total_rarity if total_rarity > 0 else 1
                except Exception:
                    w = 1
            weights.append(max(1, int(w)))
        events = [e for e in events if e != "Shop"]
        if not events:
            return ([], [])
        return (events, weights)
    pool, pool_weights = build_event_pool()
    if not pool:
        print("weather_scheduler: no weather events configured or discovered; scheduler will not run.")
        return
    print("weather_scheduler: started, events pool:", list(zip(pool, pool_weights)))
    while True:
        wait_minutes = random.randint(min_i, max_i)
        pool, pool_weights = build_event_pool()
        if pool:
            try:
                event_name = random.choices(pool, weights=pool_weights, k=1)[0]
            except Exception:
                event_name = random.choice(pool)
        else:
            event_name = None
        try:
            if event_name:
                next_time = datetime.now(timezone.utc) + timedelta(minutes=wait_minutes)
                weatherstate.set_next_event(next_time, event_name)
        except Exception:
            pass

        await asyncio.sleep(wait_minutes * 60)

        if event_name:
            try:
                weatherstate.clear_next_event()
            except Exception:
                pass
            try:
                module["roll"].active_event = event_name
            except Exception:
                pass

            try:
                end_time = datetime.now(timezone.utc) + timedelta(minutes=duration_m)
                weatherstate.set_current_event_end(end_time, event_name)
            except Exception:
                pass

            msg = f"A {event_name} event has started! It will last {duration_m} minutes."
            try:
                if ann_channels:
                    for cid in ann_channels:
                        try:
                            ch = bot.get_channel(int(cid))
                            if ch and isinstance(ch, discord.TextChannel):
                                if ch.permissions_for(ch.guild.me).send_messages:
                                    await ch.send(msg)
                        except Exception:
                            pass
                else:
                    for g in bot.guilds:
                        if g.system_channel and g.system_channel.permissions_for(g.me).send_messages:
                            await g.system_channel.send(msg)
            except Exception:
                pass

            try:
                await asyncio.sleep(duration_m * 60)
            except asyncio.CancelledError:
                try:
                    module["roll"].active_event = None
                except Exception:
                    pass
                try:
                    weatherstate.clear_current_event()
                except Exception:
                    pass
                return

            try:
                if module["roll"].active_event == event_name:
                    module["roll"].active_event = None
            except Exception:
                pass
            try:
                weatherstate.clear_current_event()
            except Exception:
                pass
            end_msg = f"The {event_name} event has ended."
            try:
                if ann_channels:
                    for cid in ann_channels:
                        try:
                            ch = bot.get_channel(int(cid))
                            if ch and isinstance(ch, discord.TextChannel):
                                if ch.permissions_for(ch.guild.me).send_messages:
                                    await ch.send(end_msg)
                        except Exception:
                            pass
                else:
                    for g in bot.guilds:
                        if g.system_channel and g.system_channel.permissions_for(g.me).send_messages:
                            await g.system_channel.send(end_msg)
            except Exception:
                pass
        else:
            continue

async def load_commands():
    commands = ""
    for i in cogs:
        bot.tree.add_command(i)
        commands += f"{i.name}, "
    synced = await bot.tree.sync()
    print(f"Synced {len(synced)} commands: {commands[:-2]}")

@bot.event
async def on_ready():
    await init_db()
    await module["roll"].calculate_rarities()
    print(f"{bot.user} connected")
    await load_commands()
    try:
        bot.loop.create_task(weather_scheduler(bot))
    except Exception as e:
        print("Failed to start weather scheduler:", e)

dev_mode = True

if not dev_mode:
    bot.run(TOKEN)
else:
    bot.run(DEV_TOKEN)