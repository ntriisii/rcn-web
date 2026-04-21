import click
import json
import requests


@click.command()
@click.pass_context
def describe(ctx):
    """Describe target and show available storages."""
    base_url = ctx.obj["base_url"]
    payload = {"action": "describe_target", "params": {}}
    try:
        resp = requests.post(f"{base_url}/mcp/action", json=payload)
        resp.raise_for_status()
        click.echo(json.dumps(resp.json(), indent=2))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
