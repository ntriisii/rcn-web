import click
import json
import os
from pathlib import Path
from ruamel.yaml import YAML
import requests


@click.command()
@click.option("--name", required=True, help="Event name")
@click.option("--schedule", required=True, help="Schedule string (cron or interval)")
@click.option("--code", required=True, help="Python code for the event")
@click.option("--description", default="", help="Event description")
@click.option("--filename", help="Python filename to save code")
@click.option(
    "--run-now", is_flag=True, help="Execute the code immediately after scheduling"
)
@click.pass_context
def schedule_fn(ctx, name, schedule, code, description, filename, run_now):
    """Create or update a scheduled function in the flow YAML and optionally run it now."""

    if not filename:
        filename = f"{name.replace('-', '_')}.py"
    file_path = Path(filename)

    with open(file_path, "a") as f:
        if file_path.exists() and file_path.stat().st_size > 0:
            f.write("\n\n")
        f.write(code)
    click.echo(f"Saved Python code to {filename}")

    yaml_path = Path("basic_recon_flow.yaml")
    yaml_obj = YAML()
    if yaml_path.exists():
        with open(yaml_path, "r") as f:
            data = yaml_obj.load(f) or {}
    else:
        data = {}
    if "time-events" not in data:
        data["time-events"] = []
    events = data["time-events"]
    existing_event = next((e for e in events if e.get("name") == name), None)
    new_event = {
        "name": name,
        "every": schedule,
        "enabled": True,
        "description": description,
        "function": f"py_{Path(filename).stem}",
    }
    if existing_event:
        existing_event.update(new_event)
    else:
        events.append(new_event)
    with open(yaml_path, "w") as f:
        yaml_obj.dump(data, f)
    click.echo(f"Updated {yaml_path}")

    if run_now:
        fn_name = Path(filename).stem
        exec_code = f"{code}\n\nimport asyncio\nif __name__ == '__main__': asyncio.run({fn_name}({{'name': '{name}'}}, {{}}))"
        base_url = ctx.obj["base_url"]
        try:
            resp = requests.post(f"{base_url}/mcp/run_script", json={"code": exec_code})
            resp.raise_for_status()
            click.echo("Executed immediately")
        except Exception as e:
            click.echo(f"Execution error: {e}", err=True)
