"""``runway gen-sample cfn` command."""
import logging
from pathlib import Path
from typing import Any

import click

from ... import options
from .utils import TEMPLATES, copy_sample, write_tfstate_template

LOGGER = logging.getLogger(__name__.replace("._", "."))


@click.command("cfn", short_help="cfngin + cfn (sampleapp.cfn)")
@options.debug
@options.no_color
@options.verbose
@click.pass_context
def cfn(ctx, **_):
    # type: (click.Context, Any) -> None
    """Generate a sample CFNgin project using CloudFormation."""
    src = TEMPLATES / "cfn"
    dest = Path.cwd() / "sampleapp.cfn"
    templates = dest / "templates"
    tf_state = templates / "tf_state.yml"

    copy_sample(ctx, src, dest)
    templates.mkdir()
    write_tfstate_template(tf_state)
    LOGGER.success("Sample CloudFormation module created at %s", dest)
