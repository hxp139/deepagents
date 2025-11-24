"""DeepAgents CLI - Interactive AI coding assistant."""

__all__ = ["cli_main"]


def __getattr__(name):
    if name == "cli_main":
        from deepagents_cli.main import cli_main

        return cli_main
    raise AttributeError(name)
