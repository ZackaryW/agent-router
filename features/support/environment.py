from pathlib import Path
from tempfile import TemporaryDirectory
import os


def before_scenario(context, scenario) -> None:
    context._temporary_directory = TemporaryDirectory()
    context.root = Path(context._temporary_directory.name)
    context.home = context.root / "home"
    context.home.mkdir()
    context._original_home = os.environ.get("HOME")
    os.environ["HOME"] = str(context.home)
    context.destination = context.root / "destination"
    context.error = None
    context.result = None


def after_scenario(context, scenario) -> None:
    if context._original_home is None:
        os.environ.pop("HOME", None)
    else:
        os.environ["HOME"] = context._original_home
    context._temporary_directory.cleanup()
