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


from .commands import preview, annotate, delegate, scan, describe


cli.add_command(preview.preview)
cli.add_command(preview.view)
cli.add_command(preview.add)
cli.add_command(preview.update)
cli.add_command(preview.delete)
cli.add_command(preview.prompt)
cli.add_command(preview.action)
cli.add_command(preview.list_tools)
cli.add_command(preview.list_prompts)
cli.add_command(annotate.annotate)
cli.add_command(delegate.delegate)
cli.add_command(scan.scan)
cli.add_command(scan.fuzz)
cli.add_command(describe.describe_target)


def main():
    cli()
