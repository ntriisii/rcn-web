import click
import os

RCN_SERVER_URL = os.environ.get("RCN_WEB_URL", "http://localhost:8023")


@click.group()
@click.option("--base-url", default=RCN_SERVER_URL, help="RCN server URL")
@click.pass_context
def cli(ctx, base_url):
    """RCN Web CLI tool."""
    ctx.ensure_object(dict)
    ctx.obj["base_url"] = base_url


from .commands import preview, annotate, delegate, scan, schedule


cli.add_command(preview.preview)
cli.add_command(preview.view)
cli.add_command(annotate.add_note)
cli.add_command(annotate.annotate)
cli.add_command(delegate.delegate)
cli.add_command(scan.scan)
cli.add_command(scan.fuzz)
cli.add_command(schedule.schedule_fn)


def main():
    cli()
