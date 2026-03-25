import click
import json
import requests


@click.command()
@click.option("--app", required=True, help="Application name")
@click.option("--entry-id", required=True, help="Entry ID")
@click.option("--key", required=True, help="Note key")
@click.option("--value", required=True, help="Note value")
@click.option("--storage", default="web-apps::annotations", help="Storage name")
@click.option("--category", default="notes", help="Note category")
@click.pass_context
def add_note(ctx, app, entry_id, key, value, storage, category):
    """Add a note annotation to an entry."""
    base_url = ctx.obj["base_url"]
    payload = {
        "app_name": [app],
        "storage_name": [storage] if storage else [],
        "entry_id": entry_id,
        "key": key,
        "value": value,
        "category": category,
    }
    try:
        resp = requests.post(f"{base_url}/storage/addEntryAnnotation", json=payload)
        resp.raise_for_status()
        click.echo(json.dumps(resp.json(), indent=2))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@click.command()
def annotate():
    """Placeholder for annotate command."""
    click.echo("annotate command not implemented yet")
