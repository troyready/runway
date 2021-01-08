"""``runway gen-sample static-angular`` command."""
import logging
from pathlib import Path
from typing import Any

import click

from ... import options
from .utils import TEMPLATES, convert_gitignore, copy_sample

LOGGER = logging.getLogger(__name__.replace("._", "."))


@click.command("static-angular", short_help="angular static site (static-angular)")
@options.debug
@options.no_color
@options.verbose
@click.pass_context
def static_angular(ctx, **_):
    # type: (click.Context, Any) -> None
    """Generate a sample static site project using Angular."""
    src = TEMPLATES / "static-angular"
    dest = Path.cwd() / "static-angular"

    copy_sample(ctx, src, dest)
    convert_gitignore(dest / "sampleapp.web/_gitignore")

    LOGGER.success("Sample static Angular site repo created at %s", dest)
    LOGGER.notice("See the README for setup and deployment instructions.")
