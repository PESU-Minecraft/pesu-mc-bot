import os
from dotenv import load_dotenv

import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone

from utils import (
    is_admin,
    get_player_count,
    start_vm,
    stop_vm,
    stop_mc_server,
    get_vm_status,
    format_duration,
)
from webserver import run_webserver
from stats.graphs import plot_metric
from stats.mongo import server_metrics, players
from datetime import datetime, timezone

import threading

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="$", intents=intents)
empty_time = None
trigger_shutdown = False

VOTE_EMOJI = "👍"
REQUIRED_VOTES = 4

active_vote_message_id = None
current_votes = set()


CLOCK = "<a:Minecraft_clock:1462830831092498671>"
PARROT = "<a:dancing_parrot:1462833253692997797>"
CHEST = "<a:MinecraftChestOpening:1462837623625355430>"
TNT = "<a:TNT:1462841582376980586>"
FLAME = "<a:animated_flame:1462846702191907013>"
SAD = "<:jeb_screm:1462848647149519145>"
RED_DOT = "🔴"
GREEN_DOT = "🟢"


def embed_starting():
    """
    STACK: Discord information
    Send an `Embed` acknowledgment when the server is starting.

    Returns:
        Embed (Discord obj)
    """
    return (
        discord.Embed(
            title=f"{CLOCK} Starting PESU Minecraft Server",
            description=(
                "Your beloved server is booting up!\n\n"
                f"This may take a while {PARROT}"
            ),
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc),
        )
        .set_footer(text="Xymic")
        .set_thumbnail(
            url="https://images-ext-1.discordapp.net/external/7nIEsery5zNVdedxw1ZE4KbpDsdbynTfKfBiVvBxH4k/%3Fsize%3D4096/https/cdn.discordapp.com/icons/1406919525831540817/0c5be54039c065ad713c2e60cdcf1d3d.png?format=webp&quality=lossless&width=579&height=579"
        )
    )


def embed_started():
    """
    STACK: Discord information
    Send an `Embed` acknowledgment when the server has started.

    Returns:
        Embed (Discord obj)
    """
    return discord.Embed(
        title="✅ Server Online",
        description=(f"Get in losers - the server is going live! {CHEST}"),
        color=discord.Color.green(),
        timestamp=datetime.now(timezone.utc),
    ).set_footer(text="Xymic")


def embed_manual_stop():
    """
    STACK: Discord information
    Send an `Embed` acknowledgment when the server is shutting down.

    Returns:
        Embed (Discord obj)
    """
    return discord.Embed(
        title=f"{TNT} Server Shutdown Requested",
        description=("The Minecraft server is now shutting down.\n"),
        color=discord.Color.orange(),
        timestamp=datetime.now(timezone.utc),
    ).set_footer(text="Xymic")


def embed_auto_shutdown():
    """
    STACK: Discord information
    Send an `Embed` acknowledgment when the server stops automatically.

    Returns:
        Embed (Discord obj)
    """
    return discord.Embed(
        title=f"{SAD} Server Idle",
        description=(
            "The server has been empty for **1 minute**.\n"
            "Initiating automatic shutdown sequence…"
        ),
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc),
    ).set_footer(text="Xymic")


def embed_stopped():
    """
    STACK: Discord information
    Send an `Embed` acknowledgment when the server has shut down.

    Returns:
        Embed (Discord obj)
    """
    return (
        discord.Embed(
            title="❌ Server Stopped",
            description=(
                "The Minecraft server has been stopped successfully.\n\n"
                f"{FLAME} The VM is now powering off to save resources."
            ),
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc),
        )
        .set_footer(text="Xymic")
        .set_thumbnail(
            url="https://images-ext-1.discordapp.net/external/7nIEsery5zNVdedxw1ZE4KbpDsdbynTfKfBiVvBxH4k/%3Fsize%3D4096/https/cdn.discordapp.com/icons/1406919525831540817/0c5be54039c065ad713c2e60cdcf1d3d.png?format=webp&quality=lossless&width=579&height=579"
        )
    )


def embed_no_permission():
    """
    STACK: Discord permissions
    Send an `Embed` acknowledgment when the user doesn't have permissions to run the command.

    Returns:
        Embed (Discord obj)
    """
    return discord.Embed(
        title="🚫 Permission Denied",
        description=(
            "You don’t have permission to use this command.\n\n"
            "🔐 This action is restricted to server admins only."
        ),
        color=discord.Color.dark_red(),
        timestamp=datetime.now(timezone.utc),
    ).set_footer(text="Xymic")


def embed_vote_start():
    return discord.Embed(
        title="🗳️ Vote to Start Server",
        description=(
            f"React with {VOTE_EMOJI} to start the Minecraft server.\n\n"
            f"Votes needed: **{REQUIRED_VOTES+1}**"
        ),
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc),
    ).set_footer(text="Xymic")


def embed_vm_stop():
    """
    STACK: VM control
    Send an `Embed` acknowledgment when the Google VM stops.

    Returns:
        Embed (Discord obj)
    """
    return discord.Embed(
        title="The VM has been stopped.",
        color=discord.Color.red(),
        timestamp=datetime.now(timezone.utc),
    ).set_footer(text="Xymic")


@bot.event
async def on_ready():
    """
    STACK: Discord Bot
    Login acknowledgement and start timers for `check_server`
    """
    print(f"Logged in as {bot.user}")
    check_server.start()


@bot.event
async def on_reaction_add(reaction, user):
    global current_votes, active_vote_message_id

    if user.bot:
        return
    if active_vote_message_id is None:
        return
    if reaction.message.id != active_vote_message_id:
        return
    if str(reaction.emoji) != VOTE_EMOJI:
        return
    if user.id in current_votes:
        return

    current_votes.add(user.id)

    print(f"Votes: {len(current_votes)}/{REQUIRED_VOTES}")

    if len(current_votes) >= REQUIRED_VOTES:
        channel = reaction.message.channel
        active_vote_message_id = None
        current_votes.clear()

        await channel.send(embed=embed_starting())
        await start_vm()
        await channel.send(embed=embed_started())


@bot.command()
async def start(ctx):
    """
    STACK: Server control
    Starts the minecraft server if the user is admin, if not,
    make a poll to get 4+ votes in order to start the server.

    """
    global active_vote_message_id, current_votes
    if is_admin(ctx):
        await ctx.reply(embed=embed_starting())
        await start_vm()
        await ctx.reply(embed=embed_started())
        return

    else:
        current_votes = set()
        vote_message = await ctx.reply(embed=embed_vote_start())
        active_vote_message_id = vote_message.id
        await vote_message.add_reaction(VOTE_EMOJI)


@bot.command()
async def stop(ctx):
    """
    STACK: Server control
    Stop the server.
    """
    if not is_admin(ctx):
        await ctx.reply(embed=embed_no_permission())
        return
    await ctx.reply(embed=embed_manual_stop())
    await shutdown_server(manual=True)


@tasks.loop(seconds=10)
async def check_server():
    """
    STACK: Server control
    Poll to check if server has no members for longer than a minute and shutdown accordingly.
    """
    global empty_time, trigger_shutdown
    status = await get_vm_status()

    if status == "RUNNING":
        player_count = await get_player_count()
        if player_count is None:
            return

        print(f"Players online: {player_count}")
        if player_count == 0:
            if empty_time is None:
                empty_time = datetime.now()
            else:
                elapsed = (datetime.now() - empty_time).total_seconds()
                if elapsed >= 60 and not trigger_shutdown:
                    trigger_shutdown = True
                    await shutdown_server()
        else:
            empty_time = None
            trigger_shutdown = False
    else:
        print("Server is off")


@bot.command()
async def stats(ctx, mode=None, player=None):
    """
    STACK: Stats
    Bot command definition for `stats`.
    - If no mode is passed (or unknown mode), return syntax.
    - If the mode is `server`, call stats_server
    - If the mode is player, call stats_player

    Arguments:
        ctx: Message object
        mode: Whether to get server information or induvidual player information
        player: The player for which information is to be retreived.
    """
    if mode is None:
        await ctx.reply("Usage: `$stats server` or `$stats player <name>`")
        return

    if mode.lower() == "server":
        await stats_server(ctx)
    elif mode.lower() == "player":
        if not player:
            await ctx.reply("Usage: `$stats player <username>`")
            return
        await stats_player(ctx, player)
    else:
        await ctx.reply("Unknown option. Use `server` or `player`.")


@bot.command()
async def graph(ctx, metric=None, minutes=60):
    """
    STACK: Stats
    Bot command definition for `graph`. Parses user command and returns
    matplotlib graph as a file attachment and deletes the file once sent to the user.

    Arguments:
        ctx: Message object
        metric: CPU, RAM, CHUNKS, JOINS, DEATHS or PLAYERS
        minutes: The amount of time to get datapoints for relative to current time.
                Ex: 60mins = data points from 60 minutes ago to now.
    """
    if not metric:
        await ctx.reply(
            "Usage: `$graph <metric> [minutes]`\n"
            "Examples:\n"
            "`$graph player_count`\n"
            "`$graph cpu_load 30`"
        )
        return

    metric_map = {
        "players": ("player_count", "Players Online", 1),
        "cpu": ("cpu_load", "CPU Load (%)", 100),
        "ram": ("ram_used_mb", "RAM Used (MB)", 1),
        "chunks": ("loaded_chunks", "Loaded Chunks", 1),
        "joins": ("total_joins", "Total Joins", 1),
        "deaths": ("total_deaths", "Total Deaths", 1),
    }

    if metric not in metric_map:
        await ctx.reply(f"Unknown metric.\nAvailable: {', '.join(metric_map.keys())}")
        return

    col, label, scale = metric_map[metric]

    path = plot_metric(
        col,
        minutes=minutes,
        ylabel=label,
        multiply=scale,
    )

    if not path:
        await ctx.reply("No data available for that time range.")
        return

    file = discord.File(path)
    await ctx.reply(file=file)

    try:
        os.remove(path)
    except Exception as e:
        print(f"[WARN] Failed to delete graph file {path}: {e}")


async def stats_server(ctx):
    """
    STACK: Stats
    Fetches the server statistics from MongoDB. Constructs discord embed and
    returns to message as reply.

    Arguments:
        ctx: Message object
    """
    doc = server_metrics.find_one(sort=[("timestamp", -1)])

    if not doc:
        embed = discord.Embed(
            title=f"{RED_DOT} Minecraft Server Stats",
            description="No data available.",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc),
        )
        await ctx.reply(embed=embed)
        return

    status = await get_vm_status()
    # status = "RUNNING"
    offline = status != "RUNNING"

    embed = discord.Embed(
        title="Minecraft Server Stats",
        color=discord.Color.red() if offline else discord.Color.green(),
        timestamp=datetime.now(timezone.utc),
    )

    if offline:
        embed.description = (
            f"{RED_DOT} Server is currently **offline**.\nShowing last known data."
        )
    else:
        embed.description = (
            f"{GREEN_DOT} Server is currently **online**.\nShowing live data."
        )

    embed.add_field(name="Players Online", value=doc.get("player_count", 0))
    embed.add_field(
        name="CPU Load",
        value=f"{doc.get('cpu_load', 0) * 100:.2f}%",
    )
    embed.add_field(
        name="RAM",
        value=f"{doc.get('ram_used_mb', 0)} / {doc.get('ram_max_mb', 0)} MB",
    )
    embed.add_field(name="Threads", value=doc.get("threads", 0))
    embed.add_field(name="Loaded Chunks", value=doc.get("loaded_chunks", 0))
    embed.add_field(name="Total Joins", value=doc.get("total_joins", 0))
    embed.add_field(name="Total Deaths", value=doc.get("total_deaths", 0))
    embed.add_field(
        name="Uptime",
        value=format_duration(doc.get("uptime_ms", 0)),
        inline=False,
    )
    embed.add_field(
        name="Total Runtime",
        value=format_duration(doc.get("total_runtime_ms", 0)),
        inline=False,
    )

    await ctx.reply(embed=embed)


async def stats_player(ctx, username):
    """
    STACK: Stats
    Fetches induvidual player statistics based on username from the DB.

    Arguments:
        ctx: Message object
        username: Username of the player in the server.
    """
    doc = players.find_one({"name": {"$regex": f"^{username}$", "$options": "i"}})

    if not doc:
        await ctx.reply("Player not found.")
        return

    online = doc.get("online", False)

    embed = discord.Embed(
        title=f"Player Stats: {doc.get('name', 'Unknown')}",
        color=discord.Color.green() if online else discord.Color.red(),
        timestamp=datetime.now(timezone.utc),
    )

    embed.add_field(
        name="Status",
        value=f"{GREEN_DOT} Online" if online else f"{RED_DOT} Offline",
        inline=True,
    )
    embed.add_field(
        name="Playtime",
        value=format_duration(doc.get("total_playtime_ms", 0)),
        inline=True,
    )
    embed.add_field(name="Total Joins", value=doc.get("total_joins", 0), inline=True)
    embed.add_field(name="Deaths", value=doc.get("total_deaths", 0), inline=True)
    embed.add_field(name="Player Kills", value=doc.get("player_kills", 0), inline=True)
    embed.add_field(name="Mob Kills", value=doc.get("mob_kills", 0), inline=True)
    embed.add_field(name="Messages", value=doc.get("messages_sent", 0), inline=True)
    embed.add_field(
        name="Advancements", value=doc.get("advancement_count", 0), inline=True
    )
    first_join = doc.get("first_join_ts")
    last_seen = doc.get("last_seen_ts")
    embed.add_field(
        name="First Join",
        value=(
            f"<t:{first_join // 1000}:R>"
            if isinstance(first_join, int) and first_join > 0
            else "-"
        ),
        inline=True,
    )

    embed.add_field(
        name="Last Seen",
        value=(
            f"<t:{last_seen // 1000}:R>"
            if isinstance(last_seen, int) and last_seen > 0
            else "-"
        ),
        inline=True,
    )
    await ctx.reply(embed=embed)


async def shutdown_server(manual=False):
    """
    STACK: Server control
    Shuts down the minecraft server.

    Arguments:
        manual: Whether the shutdown was manual or automatic (by polling).
    """
    channel = discord.utils.get(bot.get_all_channels(), name="minecraft-chat")
    if channel:
        if manual:
            pass
            # await channel.send(embed=embed_manual_stop())
        else:
            await channel.send(embed=embed_auto_shutdown())
        await stop_mc_server()
        await channel.send(embed=embed_stopped())
        await stop_vm()
        await channel.send(embed=embed_vm_stop())


threading.Thread(target=run_webserver, daemon=True).start()

bot.run(BOT_TOKEN)
