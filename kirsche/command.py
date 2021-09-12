import json
import os
import sys
from pathlib import Path

import click
from loguru import logger
from kirsche.download import list_dois, download_metadata
from kirsche.connect import append_connections
from kirsche.dataset import DataViews


logger.remove()
logger.add(sys.stderr, level="INFO", enqueue=True)


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

    dois = list_dois(paper_id, bib_file)

    if not dois:
        click.secho(
            "No DOIs input. Specify dois using `-p` or a bib file using `-b`", fg="red"
        )

    paper_info = download_metadata(dois, target, sleep_time)

    if not target:
        dv = DataViews(paper_info)
        click.echo(dv.json_simple)

    return paper_info


@kirsche.command()
@click.option("--data_file", "-d", help="path to data file with paper metadata")
@click.option("--target", "-t", help="path to save enhanced data file")
def connections(data_file, target):
    """Establish connections between the list of papers

    :param data_file: path to data file with paper metadata
    :type data_file: str
    :param target: path to save enhanced data file
    :type target: str
    """

    connected_papers = append_connections(data_file, target)

    return connected_papers


if __name__ == "__main__":
    pass
