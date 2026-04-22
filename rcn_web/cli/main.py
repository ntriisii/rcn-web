import click
import os

RCN_SERVER_URL = os.environ.get("RCN_WEB_URL", "http://localhost:8023")


@click.group()
@click.argument("target")
@click.option("--base-url", default=RCN_SERVER_URL, help="RCN server URL")
@click.pass_context
def cli(ctx, target, base_url):
    """RCN Web CLI tool."""
    ctx.ensure_object(dict)
    base_url = f"{base_url.rstrip('/')}/{target}"
    ctx.obj["base_url"] = base_url


from .commands import storage, annotate, delegate, describe


cli.add_command(storage.storage_group, name="storage")
cli.add_command(storage.preview)
cli.add_command(storage.view)
cli.add_command(storage.prompt)
cli.add_command(storage.action)
cli.add_command(storage.list_tools)
cli.add_command(storage.list_prompts)
cli.add_command(annotate.annotate)
cli.add_command(delegate.delegate)
cli.add_command(describe.describe, name="describe-target")


def main():
    cli()
