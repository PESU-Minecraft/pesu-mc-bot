import os
from dotenv import load_dotenv

import discord
from discord.ext import commands, tasks
from datetime import datetime

from utils import is_admin, get_player_count, start_vm, stop_vm, stop_mc_server, get_vm_status
from webserver import run_webserver

import threading

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='$', intents=intents)
empty_time = None
trigger_shutdown = False

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    check_server.start()


@bot.command()
async def start(ctx):
    if not is_admin(ctx):
        await ctx.reply("You can’t use this command!")
        return
    await ctx.reply("Starting Minecraft server")
    await start_vm()
    await ctx.reply("Vm has started. Get in losers mc server is starting")

@bot.command()
async def stop(ctx):
    if not is_admin(ctx):
        await ctx.reply("You can’t use this command!")
        return
    await ctx.reply("Stopping Minecraft server")
    await shutdown_server(manual=True)
    

@tasks.loop(seconds=10)
async def check_server():
    global empty_time, trigger_shutdown
    status = await get_vm_status()    

    if status == "RUNNING":
        player_count = await get_player_count()
        if player_count is None:
            return 

        print(f'Players online: {player_count}')
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


async def shutdown_server(manual=False):
    channel = discord.utils.get(bot.get_all_channels(), name='minecraft-chat')
    if channel:
        if manual:
            await channel.send('Server stop command received from admin. Stopping Minecraft server...')
        else:
            await channel.send('Server has been empty for 1 minute. Initiating automatic shutdown.')
        await stop_mc_server()
        await channel.send("Server stopped. Turning off vm now")
        await stop_vm()
        await channel.send("Vm has been turned off")



threading.Thread(target=run_webserver).start()

bot.run(BOT_TOKEN)
