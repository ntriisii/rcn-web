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
        if "application/json" in resp.headers.get("Content-Type", ""):
            click.echo(json.dumps(resp.json(), indent=2))
        else:
            click.echo(resp.text)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
