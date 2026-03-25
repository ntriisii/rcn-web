import click
import json
import requests


@click.command()
@click.option("--storage", required=True, help="Storage name")
@click.option("--app", required=True, help="Application name")
@click.option("--data", required=True, help="JSON data to add")
@click.pass_context
def add(ctx, storage, app, data):
    """Add data to storage via /storage/addContent endpoint."""
    base_url = ctx.obj["base_url"]
    try:
        json_data = json.loads(data)
        if not isinstance(json_data, list):
            json_data = [json_data]
    except json.JSONDecodeError:
        click.echo("Error: Invalid JSON data", err=True)
        return
    payload = {"query-string": storage, "data": json_data}
    try:
        resp = requests.post(f"{base_url}/storage/addContent", json=payload)
        resp.raise_for_status()
        click.echo("Data added successfully")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
