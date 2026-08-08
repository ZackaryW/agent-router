from pathlib import Path
from tempfile import TemporaryDirectory


def before_scenario(context, scenario) -> None:
    context._temporary_directory = TemporaryDirectory()
    context.root = Path(context._temporary_directory.name)
    context.home = context.root / "home"
    context.home.mkdir()
    context.destination = context.root / "destination"
    context.error = None
    context.result = None


def after_scenario(context, scenario) -> None:
    context._temporary_directory.cleanup()
