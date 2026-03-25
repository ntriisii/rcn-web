import click
import json
import requests


@click.command()
@click.option("--storage", required=True, help="Storage name")
@click.option("--app-id", type=int, help="Application ID")
@click.option("--filter", "sql_filter", help="SQL filter expression")
@click.pass_context
def preview(ctx, storage, app_id, sql_filter):
    """Preview storage before viewing."""
    base_url = ctx.obj["base_url"]
    payload = {"type": storage}
    if app_id:
        payload["parent_id"] = app_id
    if sql_filter:
        payload["sql_filter"] = sql_filter
    try:
        resp = requests.post(f"{base_url}/mcp/preview/generic", json=payload)
        resp.raise_for_status()
        click.echo(json.dumps(resp.json(), indent=2))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@click.command()
@click.option("--storage", required=True, help="Storage name")
@click.option("--app-id", type=int, help="Application ID")
@click.option("--page", default=1, help="Page number")
@click.option("--limit", default=1000, help="Results per page")
@click.option("--filter", "sql_filter", help="SQL filter expression")
@click.pass_context
def view(ctx, storage, app_id, page, limit, sql_filter):
    """View storage entries with pagination."""
    base_url = ctx.obj["base_url"]
    payload = {"type": storage, "page": page, "limit": limit}
    if app_id:
        payload["parent_id"] = app_id
    if sql_filter:
        payload["sql_filter"] = sql_filter
    try:
        resp = requests.post(f"{base_url}/mcp/view/generic", json=payload)
        resp.raise_for_status()
        click.echo(json.dumps(resp.json(), indent=2))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
