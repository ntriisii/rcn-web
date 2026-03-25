import click
import json
import requests


@click.command()
@click.option("--storage", required=True, help="Storage name")
@click.option("--entry-id", required=True, help="Entry ID")
@click.option("--category", required=True, help="Annotation category")
@click.option("--key", required=True, help="Note key")
@click.option("--value", required=True, help="Note value")
@click.pass_context
def annotate(ctx, storage, entry_id, category, key, value):
    """Add an annotation to an entry."""
    base_url = ctx.obj["base_url"]
    payload = {
        "storage_name": [storage],
        "entry_id": entry_id,
        "category": category,
        "key": key,
        "value": value,
    }
    try:
        resp = requests.post(f"{base_url}/storage/addEntryAnnotation", json=payload)
        resp.raise_for_status()
        click.echo(json.dumps(resp.json(), indent=2))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
