import pytest
import click
import requests
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from rcn_web.cli.main import cli

def test_cli_target_argument_mandatory():
    runner = CliRunner()
    result = runner.invoke(cli, [])
    assert result.exit_code != 0
    # It might just show usage if no arguments provided
    assert "Usage: cli" in result.output
    assert "TARGET" in result.output

def test_cli_base_url_formation():
    runner = CliRunner()
    
    @cli.command()
    @click.pass_context
    def check_url(ctx):
        click.echo(f"URL: {ctx.obj['base_url']}")

    result = runner.invoke(cli, ["test-target", "check-url"])
    assert result.exit_code == 0
    assert "URL: http://localhost:8023/test-target" in result.output

def test_describe_target_command_uses_target_base_url():
    runner = CliRunner()
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"target": {}, "storages": {}}
        
        result = runner.invoke(cli, ["my-recon", "describe-target", "--target", "site-123"])
        
        assert result.exit_code == 0
        args, kwargs = mock_post.call_args
        assert args[0] == "http://localhost:8023/my-recon/mcp/describe-target"
        assert kwargs["json"] == {"target": "site-123"}

def test_cli_with_custom_base_url():
    runner = CliRunner()
    @cli.command()
    @click.pass_context
    def check_url_2(ctx):
        click.echo(f"URL: {ctx.obj['base_url']}")

    result = runner.invoke(cli, ["--base-url", "http://remote:9000/", "remote-target", "check-url-2"])
    assert result.exit_code == 0
    assert "URL: http://remote:9000/remote-target" in result.output

def test_preview_command_uses_target_base_url():
    runner = CliRunner()
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"count": 10}
        
        result = runner.invoke(cli, ["my-target", "preview", "--storage", "web-apps"])
        
        assert result.exit_code == 0
        args, kwargs = mock_post.call_args
        assert args[0] == "http://localhost:8023/my-target/mcp/preview"

def test_view_command_uses_target_base_url():
    runner = CliRunner()
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = []
        
        result = runner.invoke(cli, ["my-target", "view", "--storage", "web-apps", "--limit", "10"])
        
        assert result.exit_code == 0
        args, kwargs = mock_post.call_args
        assert args[0] == "http://localhost:8023/my-target/mcp/view"
        assert kwargs["json"]["limit"] == 10
