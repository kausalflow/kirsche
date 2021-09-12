import json
import os
import sys
from pathlib import Path

import click
import inquirer
from loguru import logger
from rich.console import Console
from kirsche.download import download
from kirsche.connect import connect



logger.remove()
logger.add(sys.stderr, level="INFO", enqueue=True)
console = Console()


__CWD__ = os.getcwd()


@click.group(invoke_without_command=True)
@click.pass_context
def kirsche(ctx):
    if ctx.invoked_subcommand is None:
        click.echo("Hello {}".format(os.environ.get("USER", "")))
        click.echo("Welcome to Kirsche.")
    else:
        pass


@kirsche.command()
@click.option("--paper_id", "-p", help="Paper ID", multiple=True)
@click.option("--bib_file", "-b", help="Bib file path")
@click.option("--target", "-t", help="Target data file path")
@click.option("--sleep_time", "-s", default=1, help="Sleep time between requests")
def metadata(paper_id, bib_file, target, sleep_time):
    """Download paper data from service provides (e.g., SemanticScholar).

    There are two ways to provide a list of DOIs to be retrieved, provide paper DOIs directly using `--paper_id` or `-p`, or loading a bib file using `--bib_file` or `-b`.

    To save the downloaded data, provide a path to a file using `--target` or `-t`.

    :param paper_id: Paper DOI, optional, can be multiple
    :type paper_id: str
    :param bib_file: Bib file path, optional
    :type bib_file: str
    :param target: Target data file path, optional
    :type target: str
    :param sleep_time: Sleep time between requests, defaults to 1sec.
    :type sleep_time: int
    """

    paper_info = download(paper_id, bib_file, target, sleep_time)

    return paper_info


@kirsche.command()
@click.option("--data_file", "-d", help="path to data file with paper metadata")
@click.option("--target", "-t", help="path to save enhanced data file")
def connections(data_file, target):

    connect(data_file, target)



if __name__ == "__main__":
    pass