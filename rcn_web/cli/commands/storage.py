import click
import json
import requests
from rcn_core.cli.shared import (
    storage_group, 
    storage_preview as preview, 
    storage_view as view,
    storage_annotate as annotate
)

@click.command()
@click.option("--name", required=True, help="Prompt name")
@click.option("--args", help="JSON arguments for the prompt")
@click.pass_context
def prompt(ctx, name, args):
    """Execute a prompt function."""
    base_url = ctx.obj["base_url"]
    arguments = json.loads(args) if args else {}

    payload = {"prompt_name": name, "arguments": arguments}
    try:
        resp = requests.post(f"{base_url}/mcp/prompt", json=payload)
        resp.raise_for_status()
        click.echo(resp.text)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)

@click.command()
@click.option("--name", required=True, help="Action name")
@click.option("--params", help="JSON parameters for the action")
@click.pass_context
def action(ctx, name, params):
    """Execute an action."""
    base_url = ctx.obj["base_url"]
    parameters = json.loads(params) if params else {}

    payload = {"action": name, "params": parameters}
    try:
        resp = requests.post(f"{base_url}/mcp/action", json=payload)
        resp.raise_for_status()
        click.echo(json.dumps(resp.json(), indent=2))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


