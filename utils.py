from dotenv import load_dotenv
from mcstatus import JavaServer
import asyncio
import os
from google.cloud import compute_v1
from google.oauth2 import service_account
import json
import base64
import aiohttp

load_dotenv()
ADMIN_ID = [int(rid.strip()) for rid in os.getenv("ADMIN_ID").split(",")]
SERVER_IP = os.getenv('SERVER_IP')
GOOGLE_SERVICE_ACCOUNT_BASE64 = os.getenv("GOOGLE_SERVICE_ACCOUNT_BASE64")
PROJECT_ID = os.getenv("PROJECT_ID")
ZONE = os.getenv("ZONE")
INSTANCE_NAME = os.getenv("INSTANCE_NAME")
CRAFTY_TOKEN = os.getenv('CRAFTY_TOKEN')
SERVER_ID = os.getenv('SERVER_ID')


key_json = json.loads(base64.b64decode(GOOGLE_SERVICE_ACCOUNT_BASE64))
credentials = service_account.Credentials.from_service_account_info(key_json)
instances_client = compute_v1.InstancesClient(credentials=credentials)

def is_admin(ctx):
    return any(role.id in ADMIN_ID for role in ctx.author.roles)

async def get_player_count():
    """Run blocking mcstatus code in a background thread."""
    try:
        def query():
            server = JavaServer.lookup(SERVER_IP)
            status = server.status()
            return status.players.online

        return await asyncio.to_thread(query)
    except TimeoutError:
        pass
    except Exception as e:
        print(f"Error checking server status: {e}")
        return None
    
async def start_vm():
    print(f"Starting {INSTANCE_NAME}")
    operation = instances_client.start(
        project=PROJECT_ID,
        zone=ZONE,
        instance=INSTANCE_NAME
    )
    operation.result()
    print("VM started")

async def stop_vm():
    print(f"Stopping {INSTANCE_NAME}...")
    def send_command():
        operation = instances_client.stop(
            project=PROJECT_ID,
            zone=ZONE,
            instance=INSTANCE_NAME
        )
        operation.result()
    result = await asyncio.to_thread(send_command)
    print("VM stopped.")

async def get_vm_status():
    instance = instances_client.get(project=PROJECT_ID, zone=ZONE, instance=INSTANCE_NAME)
    return instance.status

async def stop_mc_server():
    headers = {"Authorization": f"{CRAFTY_TOKEN}","Content-Type": "application/json"}
    url = f"https://pesu-mc.ddns.net:8443/api/v2/servers/{SERVER_ID}/action/stop_server"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, ssl=False) as resp:
            text = await resp.text()
            print(f"[Shutdown] Response {resp.status}: {text}")
            if resp.status != 200:
                raise Exception(f"Failed to shut down server: {resp.status}")