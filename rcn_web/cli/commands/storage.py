import click
import json
import requests


@click.command()
@click.option("--storage", required=True, help="Storage name")
@click.option("--app-id", type=int, help="Application ID")
@click.option("--filter", "sql_filter", help="SQL filter expression")
@click.pass_context
def preview(ctx, storage, app_id, sql_filter):
    """Preview storage."""
    base_url = ctx.obj["base_url"]
    payload = {"collection": storage}
    if app_id:
        payload["parent_id"] = app_id
    if sql_filter:
        payload["filter"] = sql_filter
    try:
        resp = requests.post(
            f"{base_url}/mcp/preview",
            json=payload,
        )
        resp.raise_for_status()
        click.echo(resp.text)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@click.command()
@click.option("--storage", required=True, help="Storage name")
@click.option("--app-id", type=int, help="Application ID")
@click.option("--page", default=1, help="Page number")
@click.option("--limit", default=1000, help="Results per page")
@click.option("--filter", "sql_filter", help="SQL filter expression")
@click.option("--sort-by", help="Field to sort by")
@click.option(
    "--sort-order",
    type=click.Choice(["asc", "desc"]),
    default="asc",
    help="Sort order (asc or desc)",
)
@click.pass_context
def view(ctx, storage, app_id, page, limit, sql_filter, sort_by, sort_order):
    """View storage entries."""
    base_url = ctx.obj["base_url"]
    payload = {
        "collection": storage,
        "page": page,
        "limit": limit,
        "sort_by": sort_by,
        "sort_order": sort_order,
    }
    if app_id:
        payload["parent_id"] = app_id
    if sql_filter:
        payload["filter"] = sql_filter
    try:
        resp = requests.post(
            f"{base_url}/mcp/view",
            json=payload,
        )
        resp.raise_for_status()
        click.echo(resp.text)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@click.command()
@click.option("--storage", required=True, help="Storage name")
@click.option("--app-id", type=int, help="Application ID")
@click.option("--data", required=True, help="JSON data to add")
@click.pass_context
def add(ctx, storage, app_id, data):
    """Add new items to a collection."""
    base_url = ctx.obj["base_url"]
    try:
        json_data = json.loads(data)
    except json.JSONDecodeError:
        click.echo("Error: Invalid JSON data", err=True)
        return

    payload = {"collection": storage, "data": json_data}
    if app_id:
        payload["parent_id"] = app_id

    try:
        resp = requests.post(f"{base_url}/mcp/add", json=payload)
        resp.raise_for_status()
        resp_data = resp.json()
        if "added_ids" in resp_data and resp_data["added_ids"]:
            click.echo("\n".join(map(str, resp_data["added_ids"])))
        else:
            click.echo(json.dumps(resp_data, indent=2))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@click.command()
@click.option("--storage", required=True, help="Storage name")
@click.option("--app-id", type=int, help="Application ID")
@click.option("--ids", help="Comma separated item IDs")
@click.option("--filter", "sql_filter", help="SQL filter expression")
@click.option("--data", required=True, help="JSON data for update")
@click.pass_context
def update(ctx, storage, app_id, ids, sql_filter, data):
    """Update existing items in a collection."""
    base_url = ctx.obj["base_url"]
    try:
        json_data = json.loads(data)
    except json.JSONDecodeError:
        click.echo("Error: Invalid JSON data", err=True)
        return

    item_ids = [int(i.strip()) for i in ids.split(",")] if ids else None

    payload = {
        "collection": storage,
        "data": json_data,
        "item_ids": item_ids,
        "filter": sql_filter,
    }
    if app_id:
        payload["parent_id"] = app_id

    try:
        resp = requests.post(f"{base_url}/mcp/update", json=payload)
        resp.raise_for_status()
        click.echo(json.dumps(resp.json(), indent=2))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@click.command()
@click.option("--storage", required=True, help="Storage name")
@click.option("--app-id", type=int, help="Application ID")
@click.option("--ids", help="Comma separated item IDs")
@click.option("--filter", "sql_filter", help="SQL filter expression")
@click.pass_context
def delete(ctx, storage, app_id, ids, sql_filter):
    """Delete items from a collection."""
    base_url = ctx.obj["base_url"]
    item_ids = [int(i.strip()) for i in ids.split(",")] if ids else None

    payload = {"collection": storage, "item_ids": item_ids, "filter": sql_filter}
    if app_id:
        payload["parent_id"] = app_id

    try:
        resp = requests.post(f"{base_url}/mcp/delete", json=payload)
        resp.raise_for_status()
        click.echo(json.dumps(resp.json(), indent=2))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


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


@click.command()
@click.pass_context
def list_tools(ctx):
    """List available tools."""
    base_url = ctx.obj["base_url"]
    try:
        resp = requests.get(f"{base_url}/mcp/tools")
        resp.raise_for_status()
        click.echo(json.dumps(resp.json(), indent=2))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@click.command()
@click.pass_context
def list_prompts(ctx):
    """List available prompts."""
    base_url = ctx.obj["base_url"]
    try:
        resp = requests.get(f"{base_url}/mcp/prompts")
        resp.raise_for_status()
        click.echo(json.dumps(resp.json(), indent=2))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
