import click
import json
import requests


@click.command()
@click.option("--target", required=True, help="Target identifier (site or app ID)")
@click.pass_context
def describe_target(ctx, target):
    """Describe target and show available storages."""
    base_url = ctx.obj["base_url"]
    payload = {"target": target}
    try:
        resp = requests.post(f"{base_url}/mcp/describe-target", json=payload)
        resp.raise_for_status()
        click.echo(json.dumps(resp.json(), indent=2))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
