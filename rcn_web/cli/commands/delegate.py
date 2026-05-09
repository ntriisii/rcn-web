import click
import json
import requests


@click.command()
@click.option("--app", required=True, help="Application name")
@click.option("--agent", required=True, help="Agent name")
@click.option("--instructions", required=True, help="Instructions for the agent")
@click.option("--storage", required=True, help="Storage name")
@click.option("--ids", help="Comma-separated entry IDs")
@click.pass_context
def delegate(ctx, app, agent, instructions, storage, ids):
    """Delegate an action to an agent for given entries."""
    base_url = ctx.obj["base_url"]
    payload = {
        "action": "delegate_to_acp",
        "params": {
            "app_name": app,
            "agent_name": agent,
            "instructions": instructions,
            "storage_name": storage,
            "entries_ids": ids,
        },
    }
    try:
        resp = requests.post(f"{base_url}/mcp/action", json=payload)
        resp.raise_for_status()
        click.echo(json.dumps(resp.json(), indent=2))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


