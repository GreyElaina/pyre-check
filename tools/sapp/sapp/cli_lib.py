# Copyright (c) Facebook, Inc. and its affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import logging
import os
from functools import wraps
from typing import Optional

import click
import click_log
import IPython
from click import Parameter, Path, argument, option
from traitlets.config import Config

from .analysis_output import AnalysisOutput
from .context import Context, pass_context
from .create_database import CreateDatabase
from .database_saver import DatabaseSaver
from .db import DB
from .extensions import prompt_extension
from .filesystem import find_root
from .interactive import Interactive
from .model_generator import ModelGenerator
from .models import PrimaryKeyGenerator
from .pipeline import Pipeline
from .server import start_server
from .trim_trace_graph import TrimTraceGraph


MARKER_DIRECTORIES = [".pyre", ".hg", ".git", ".svn"]

logger = logging.getLogger("sapp")


def require_option(current_ctx: click.Context, param_name: str) -> None:
    """Throw an exception if an option wasn't required. This is useful when its
    optional in some contexts but required for a subcommand"""

    ctx = current_ctx
    param_definition = None
    while ctx is not None:
        # ctx.command.params has the actual definition of the param. We use
        # this when raising the exception.
        param_definition = next(
            (p for p in ctx.command.params if p.name == param_name), None
        )

        # ctx.params has the current value of the parameter, as set by the user.
        if ctx.params.get(param_name):
            return
        ctx = ctx.parent

    assert param_definition, f"unknown parameter {param_name}"
    raise click.MissingParameter(ctx=current_ctx, param=param_definition)


def common_options(func):
    @click.group(context_settings={"help_option_names": ["--help", "-h"]})
    @click_log.simple_verbosity_option(logger)
    @option(
        "--repository",
        "-r",
        default=lambda: find_root(MARKER_DIRECTORIES),
        type=Path(exists=True, file_okay=False),
        help="Root of the repository (regardless of the directory analyzed)",
    )
    @option(
        "--database-name",
        "--dbname",
        callback=default_database,
        type=Path(dir_okay=False),
    )
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


def default_database(ctx: click.Context, _param: Parameter, value: Optional[str]):
    """By default, use a database at the current dir"""
    if value:
        return value

    return os.path.join(os.path.curdir, DB.DEFAULT_DB_FILE)


@click.command(
    help="interactive exploration of issues",
    context_settings={"ignore_unknown_options": True},
)
@pass_context
@click.argument("ipython_args", nargs=-1, type=click.UNPROCESSED)
def explore(ctx: Context, ipython_args):
    scope_vars = Interactive(
        database=ctx.database,
        # pyre-fixme[6]: Expected `str` for 2nd param but got `Optional[str]`.
        repository_directory=ctx.repository,
        parser_class=ctx.parser_class,
    ).setup()
    config = Config()
    config.InteractiveShellApp.extensions = [
        prompt_extension.__name__
    ] + ctx.ipython_extensions
    config.InteractiveShellApp.profile = "sapp"
    config.InteractiveShellApp.display_banner = False

    config.InteractiveShell.show_rewritten_input = False
    config.InteractiveShell.autocall = 2

    IPython.start_ipython(
        argv=ipython_args if ipython_args else [], user_ns=scope_vars, config=config
    )


@click.command(help="parse static analysis output and save to disk")
@pass_context
@option("--run-kind", type=str)
@option("--branch", type=str)
@option("--commit-hash", type=str)
@option("--job-id", type=str)
@option("--differential-id", type=int)
@option(
    "--previous-issue-handles",
    type=Path(exists=True),
    help=(
        "file containing list of issue handles to compare INPUT_FILE to "
        "(preferred over --previous-input)"
    ),
)
@option(
    "--previous-input",
    type=Path(exists=True),
    help="static analysis output to compare INPUT_FILE to",
)
@option(
    "--linemap",
    type=Path(exists=True),
    help="json file mapping new locations to old locations",
)
@option(
    "--store-unused-models",
    is_flag=True,
    help="store pre/post conditions unrelated to an issue",
)
@argument("input_file", type=Path(exists=True))
def analyze(
    ctx: Context,
    run_kind,
    branch,
    commit_hash,
    job_id,
    differential_id,
    previous_issue_handles,
    previous_input,
    linemap,
    store_unused_models,
    input_file,
):
    # Store all options in the right places
    summary_blob = {
        "run_kind": run_kind,
        "repository": ctx.repository,
        "branch": branch,
        "commit_hash": commit_hash,
        "old_linemap_file": linemap,
        "store_unused_models": store_unused_models,
    }

    if job_id is None and differential_id is not None:
        job_id = "user_input_" + str(differential_id)
    summary_blob["job_id"] = job_id

    if previous_issue_handles:
        summary_blob["previous_issue_handles"] = AnalysisOutput.from_file(
            previous_issue_handles
        )
    elif previous_input:
        previous_input = AnalysisOutput.from_file(previous_input)

    # Construct pipeline
    input_files = (AnalysisOutput.from_file(input_file), previous_input)
    pipeline_steps = [
        ctx.parser_class(),
        CreateDatabase(ctx.database),
        ModelGenerator(),
        TrimTraceGraph(),
        # pyre-fixme[6]: Expected `bool` for 2nd param but got `PrimaryKeyGenerator`.
        DatabaseSaver(ctx.database, PrimaryKeyGenerator()),
    ]
    # pyre-fixme[6]: Expected
    #  `List[tools.sapp.sapp.pipeline.PipelineStep[typing.Any, typing.Any]]` for 1st
    #  param but got `List[typing.Union[DatabaseSaver, ModelGenerator, TrimTraceGraph,
    #  tools.sapp.sapp.base_parser.BaseParser]]`.
    pipeline = Pipeline(pipeline_steps)
    pipeline.run(input_files, summary_blob)


@click.command(
    help="backend flask server for exploration of issues",
    context_settings={"ignore_unknown_options": True},
)
@option("--debug/--no-debug", default=False, help="Start Flask server in debug mode")
@option(
    "--static-resources", default=None, help="Directory to serve static resources from"
)
@pass_context
def server(ctx: Context, debug: bool, static_resources: str):
    start_server(ctx.database, debug, static_resources)


commands = [analyze, explore, server]
