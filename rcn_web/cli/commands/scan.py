import click
import json
import random
import requests


@click.command()
@click.option("--app", required=True, help="Application name")
@click.option("--xml", required=True, help="Config XML")
@click.pass_context
def scan(ctx, app, xml):
    """Schedule a scan for an application using provided XML config."""
    base_url = ctx.obj["base_url"]
    payload = {
        "app_name": [app],
        "storage_name": ["web-apps"],
        "entry_id": app,
        "key": "tool-scanning",
        "value": f"<root><source_id>cli-scan-{random.randint(1000, 9999)}</source_id>{xml}</root>",
    }
    try:
        resp = requests.post(f"{base_url}/storage/addEntryAnnotation", json=payload)
        resp.raise_for_status()
        click.echo("Scan scheduled.")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@click.command()
@click.option("--app", required=True, help="Application name")
@click.option("--xml", required=True, help="Config XML")
@click.pass_context
def fuzz(ctx, app, xml):
    """Schedule a fuzzing job for an application using provided XML config."""
    base_url = ctx.obj["base_url"]
    payload = {
        "app_name": [app],
        "storage_name": ["web-apps"],
        "entry_id": app,
        "key": "tool-fuzzing",
        "value": f"<root><source_id>cli-fuzz-{random.randint(1000, 9999)}</source_id>{xml}</root>",
    }
    try:
        resp = requests.post(f"{base_url}/storage/addEntryAnnotation", json=payload)
        resp.raise_for_status()
        click.echo("Fuzzing scheduled.")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
