import os
import sys
import httpx
import asyncio
import uvicorn
import subprocess
import requests
import time
import json
import fnmatch
from collections import defaultdict

from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse

from mitmproxy import ctx, http
from mitmproxy.http import HTTPFlow

# This is our port mapping. In a real app, this might come
# from a config file, environment variables, or a service discovery tool.
CURRENT_PORT = 8030
TARGET_TO_PORT_MAPPING = {}
RUNNING_PROCESSES = []

# Mapping of target name -> set of active websocket flows
TARGET_WS_CLIENTS = defaultdict(set)


def expand_target(target_str):
    global TARGET_TO_PORT_MAPPING

    found_targets = []
    target_list = target_str.split(",")
    for target in TARGET_TO_PORT_MAPPING:
        for t in target_list:
            if fnmatch.fnmatch(t, target):
                found_targets.append(target)

    return found_targets


async def request(flow: HTTPFlow):
    """
    This is the main reverse proxy endpoint.
    It captures the target_name and the rest of the path.
    """

    global CURRENT_PORT, TARGET_TO_PORT_MAPPING, RUNNING_PROCESSES

    print("receiving a request in here", flow.request.url)
    # scope should be all the running targets
    if flow.request.url == "http://localhost:8023/getScope":
        scope = {}
        # send the request to all the running services and parse that scope and send it
        async with httpx.AsyncClient() as client:
            for target in TARGET_TO_PORT_MAPPING:
                print("getting the freaking scope for target", target)
                port = TARGET_TO_PORT_MAPPING[target]
                try:
                    resp = await client.get(f"http://localhost:{port}/getScope")
                    if resp.status_code == 200:
                        scope[target] = resp.json()
                except Exception as e:
                    print(f"Error getting scope for {target}: {e}")

        flow.response = http.Response.make(
            200, json.dumps(scope).encode("utf-8"), {"Content-Type": "application/json"}
        )

        return

    # collect the target name from the URL
    path_parts = flow.request.path.strip("/").split("/")
    if not path_parts:
        return
    target_name = path_parts[0]

    # Store the target name in metadata for websocket syncing
    flow.metadata["target_name"] = target_name

    if target_name not in TARGET_TO_PORT_MAPPING:
        # create the mapping
        cport = CURRENT_PORT
        recon_dir_path = os.path.expanduser(f"~/recon/{target_name}/")

        if not os.path.exists(recon_dir_path):
            flow.response = http.Response.make(
                404,  # Status code
                b'{"error": "Invalid data index provided"}',  # Response body
                {"Content-Type": "application/json"},  # Headers
            )

            return

        python_root = os.path.expanduser("~/programming-projects/python/rcn-web/")
        python_path = (os.getenv("PYTHONPATH") or "") + ":" + python_root
        python = os.path.join(python_root, ".venv/bin/python3")

        print(f"Starting rcn_web for {target_name} on port {cport}...")
        proc = await asyncio.create_subprocess_exec(
            python,
            "-m",
            "rcn_web",
            recon_dir_path,
            "--port",
            str(cport),
            env={**os.environ, "PYTHONPATH": python_path},
        )

        started = False
        async with httpx.AsyncClient() as client:
            for _ in range(20):  # Try for 10 seconds
                try:
                    # Use a very short timeout for the health check
                    resp = await client.get(f"http://localhost:{cport}", timeout=0.5)
                    if resp.status_code < 500:  # Any response is usually enough
                        started = True
                        break
                except (httpx.ConnectError, httpx.TimeoutException):
                    await asyncio.sleep(0.5)
                    continue

        if not started:
            print(f"Failed to start rcn_web for {target_name}")
            flow.response = http.Response.make(
                500,
                b'{"error": "Failed to start downstream service"}',
                {"Content-Type": "application/json"},
            )
            return

        RUNNING_PROCESSES.append(proc)
        TARGET_TO_PORT_MAPPING[target_name] = cport
        CURRENT_PORT += 1

    flow.request.host = "localhost"
    flow.request.port = TARGET_TO_PORT_MAPPING[target_name]
    new_path = "/" + "/".join(path_parts[1:])
    flow.request.path = new_path


async def websocket_start(flow: HTTPFlow):
    target_name = flow.metadata.get("target_name")
    if target_name:
        TARGET_WS_CLIENTS[target_name].add(flow)
        print(f"Websocket client connected for target: {target_name}")


async def websocket_end(flow: HTTPFlow):
    target_name = flow.metadata.get("target_name")
    if target_name and target_name in TARGET_WS_CLIENTS:
        TARGET_WS_CLIENTS[target_name].discard(flow)
        print(f"Websocket client disconnected for target: {target_name}")


def done():
    """
    Cleanup child processes when mitmproxy shuts down.
    """
    global RUNNING_PROCESSES
    print("Mitmproxy shutting down, killing child processes...")
    for proc in RUNNING_PROCESSES:
        try:
            proc.terminate()
        except Exception as e:
            print(f"Error terminating process: {e}")


async def websocket_message(flow: HTTPFlow):
    target_name = flow.metadata.get("target_name")
    if not target_name:
        return

    # Websocket Syncing Logic
    # We broadcast all messages (client -> server and server -> client)
    # to all other clients connected to the same target.
    last_message = flow.websocket.messages[-1]

    # Avoid infinite loops: mitmproxy handles injected messages normally,
    # but we should only broadcast messages that weren't injected by us.
    # However, mitmproxy doesn't easily distinguish injected messages in the event.
    # A simple way is to check if the message is from server or client.

    # Broadcast server messages to all other clients
    # Broadcast client messages to all other clients (optional, but good for sync)
    for other_flow in list(TARGET_WS_CLIENTS[target_name]):
        if other_flow != flow and other_flow.websocket.open:
            other_flow.websocket.send(last_message.content, last_message.type == 1)
