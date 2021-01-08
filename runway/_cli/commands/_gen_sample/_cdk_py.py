"""``runway gen-sample cdk-py`` command."""
import logging
from pathlib import Path
from typing import Any

import click

from ... import options
from .utils import TEMPLATES, copy_sample

LOGGER = logging.getLogger(__name__.replace("._", "."))


@click.command("cdk-py", short_help="cdk + py (sampleapp.cdk)")
@options.debug
@options.no_color
@options.verbose
@click.pass_context
def cdk_py(ctx, **_):
    # type: (click.Context, Any) -> None
    """Generate a sample AWS CDK project using python."""
    src = TEMPLATES / "cdk-py"
    dest = Path.cwd() / "sampleapp.cdk"
    copy_sample(ctx, src, dest)
    # .gitignore already exists

    LOGGER.success("Sample CDK module created at %s", dest)
    LOGGER.notice(
        "To finish it's setup, change to the %s directory and "
        'execute "npm install" to generate it\'s lockfile.',
        dest,
    )
