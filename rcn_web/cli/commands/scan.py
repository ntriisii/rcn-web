import click
import subprocess
import shlex


@click.command()
@click.option("--app", required=True, help="Application name")
@click.option("--template", help="Nuclei template")
@click.pass_context
def scan(ctx, app, template):
    """Run nuclei scan using rr command."""
    cmd = f"rr nuclei -u {app}"
    if template:
        cmd += f" -t {template}"
    subprocess.run(shlex.split(cmd), check=True)


@click.command()
@click.option("--app", required=True, help="Application name")
@click.option("--wordlist", help="Wordlist for fuzzing")
@click.pass_context
def fuzz(ctx, app, wordlist):
    """Run ffuf fuzzing using rr command."""
    cmd = f"rr ffuf -u {app}/FUZZ"
    if wordlist:
        cmd += f" -w {wordlist}"
    subprocess.run(shlex.split(cmd), check=True)
