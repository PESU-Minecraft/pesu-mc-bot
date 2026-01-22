from dotenv import load_dotenv
import yaml

from mcstatus import JavaServer
import asyncio
import os

from google.cloud import compute_v1
from google.oauth2 import service_account
import json
import base64
import aiohttp

load_dotenv()
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

ADMIN_ID = config["bot"]["ADMIN_ID"].split(",")

SERVER_IP = config["crafty"]["SERVER_IP"]
SERVER_ID = config["crafty"]["SERVER_ID"]

PROJECT_ID = config["gcp"]["PROJECT_ID"]
ZONE = config["gcp"]["ZONE"]
INSTANCE_NAME = config["gcp"]["INSTANCE_NAME"]

GOOGLE_SERVICE_ACCOUNT_BASE64 = os.getenv("GOOGLE_SERVICE_ACCOUNT_BASE64")
CRAFTY_TOKEN = os.getenv("CRAFTY_TOKEN")


key_json = json.loads(base64.b64decode(GOOGLE_SERVICE_ACCOUNT_BASE64))
credentials = service_account.Credentials.from_service_account_info(key_json)
instances_client = compute_v1.InstancesClient(credentials=credentials)


def is_admin(ctx):
    """
    STACK: Discord permissions
    Check if the user running the command is a verified administrator
    in the discord server.

    Args:
        ctx: Message object
    """
    for role in ctx.author.roles:
        if str(role.id) in ADMIN_ID:
            return True


async def get_player_count():
    """
    STACK: Server control
    Run blocking mcstatus code in a background thread.

    Returns:
        status.players.online: Number of online players.
    """
    try:

        def query():
            server = JavaServer.lookup(SERVER_IP)
            status = server.status()
            return status.players.online

        return await asyncio.to_thread(query)
    except TimeoutError:
        pass
    except Exception as e:
        print(f"[SERVER CONTROL] Error checking server status: {e}")
        return None


async def start_vm():
    """
    STACK: VM control
    Starts the virtual machine on Google cloud.
    """
    print(f"[VM CONTROL] Starting {INSTANCE_NAME}")
    operation = instances_client.start(
        project=PROJECT_ID, zone=ZONE, instance=INSTANCE_NAME
    )
    operation.result()
    print("[VM CONTROL] VM started")


async def stop_vm():
    """
    STACK: VM control
    Stops the virtual machine on Google cloud.
    """
    print(f"[VM CONTROL] Stopping {INSTANCE_NAME}...")

    def send_command():
        operation = instances_client.stop(
            project=PROJECT_ID, zone=ZONE, instance=INSTANCE_NAME
        )
        operation.result()

    result = await asyncio.to_thread(send_command)
    print("[VM CONTROL] VM stopped.")


async def get_vm_status():
    """
    STACK: VM control
    Fetches the status of the virtual machine on Google cloud.
    """
    instance = instances_client.get(
        project=PROJECT_ID, zone=ZONE, instance=INSTANCE_NAME
    )
    return instance.status


async def stop_mc_server():
    """
    STACK: Server control
    Stops the minecraft server on the VM. Requires `CRAFTY_TOKEN` and `SERVER_ID` in `.env`.
    """
    headers = {"Authorization": f"{CRAFTY_TOKEN}", "Content-Type": "application/json"}
    url = f"https://pesu-mc.ddns.net:8443/api/v2/servers/{SERVER_ID}/action/stop_server"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, ssl=False) as resp:
            text = await resp.text()
            print(f"[SERVER CONTROL] Shutdown Response {resp.status}: {text}")
            if resp.status != 200:
                raise Exception(
                    f"[SERVER CONTROL] Failed to shutdown server: {resp.status}"
                )


def format_duration(ms):
    """
    STACK: Formatting / Stats
    Formats the duration specified in ms to HH:MM:SS format.

    Args:
        ms: Time in milliseconds.
    Returns:
        str: HHh MMm SSs
    """
    seconds = ms // 1000
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}h {m:02d}m {s:02d}s"


def gb(v):
    """
    STACK: Formatting / Stats
    Convert bytes to gigabytes

    Args:
        v: Value to convert

    Returns:
        str: <value in gb> GB
    """
    return f"{v / (1024**3):.2f} GB"


async def ping_stats(player_uuid: str | None = None):
    STATS_TOKEN = os.getenv("STATS_TOKEN")
    STATS_ENDPOINT = "http://" + SERVER_IP + "/mc/stats"
    headers = {"x-stats-token": STATS_TOKEN}

    params = {}
    if player_uuid:
        params["player"] = player_uuid

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                STATS_ENDPOINT,
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=2),
            ) as resp:
                await resp.text()
    except (aiohttp.ClientConnectorError, asyncio.TimeoutError):
        return False
    except Exception as e:
        print(f"[STATS] Ping failed: {type(e).__name__}")
        return False
