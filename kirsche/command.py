import os
import sys

import click
from loguru import logger
from pyecharts.charts.base import default
from kirsche.download import list_unique_ids, download_metadata
from kirsche.connect import (
    append_connections,
    append_connections_for_file,
    save_connected_papers,
)
from kirsche.dataset import DataViews
from kirsche.utils.io import load_batch_json, record_exists
from kirsche.utils.bib import load_bib
from kirsche.visualize import make_chart, PaperGraph, visualize
from typing import Union, Optional
from pathlib import Path

logger.remove()
logger.add(sys.stderr, level="INFO", enqueue=True)


__CWD__ = os.getcwd()


def _metadata(
    paper_id: Optional[Union[list, str]],
    source_bib_file: Union[str, Path],
    target_metadata_path: Union[str, Path],
    sleep_time: Optional[int] = 1,
    existing_records: Optional[list] = []
):
    """Download paper data from service provides (e.g., SemanticScholar).

    There are two ways to provide a list of unique ids to be retrieved, provide paper DOIs directly using `--paper_id` or `-p`, or loading a bib file using `--bib_file` or `-b`.

    To save the downloaded data, provide a path to a file using `--target` or `-t`.

    :param paper_id: Paper unique ids, optional, can be multiple
    :param bib_file: Bib file path, optional
    :param target_metadata_path: Target data file path, optional
    :param sleep_time: Sleep time between requests, defaults to 1sec.
    :param existing_records: Existing records for metadata, optional
    """

    if target_metadata_path:
        logger.debug(f"Target metadata path: {target_metadata_path} exists. looking for existing metadata...")
        existing_metadata = load_batch_json(target_metadata_path)
        if existing_metadata:
            logger.debug(
                f"Found {len(existing_metadata)} records in {target_metadata_path}"
            )
    else:
        existing_metadata = []

    if existing_records:
        existing_metadata = existing_metadata + existing_records

    if existing_metadata:
        logger.debug(f"{len(existing_metadata)} existing metadta")

    click.echo(f"Retrieving unique ids...")
    logger.debug(f"loading bib {source_bib_file}")
    bib_content = load_bib(source_bib_file)
    # logger.debug(f"bib {source_bib_file} content: {bib_content}")
    if source_bib_file:
        paper_id = list_unique_ids(source_bib_file)
    elif isinstance(paper_id, str):
        paper_id = [paper_id]

    click.echo(f"  Retrieved {len(paper_id)} unique ids")

    logger.debug(f"({len(paper_id)}) Filter out existing records...")
    paper_id = [i for i in paper_id if not record_exists(i, existing_metadata)]
    logger.info(f"{len(paper_id)} ids to be downloaded")

    if not paper_id:
        click.secho(
            "No unique ids input. Specify unique ids using `-p` or a bib file using `-b`",
            fg="red",
        )

    paper_info = download_metadata(paper_id, target_metadata_path, sleep_time)

    if not target_metadata_path:
        dv = DataViews(paper_info)
        click.echo(dv.json_simple)

    return paper_info


@click.group(invoke_without_command=True)
@click.pass_context
def kirsche(ctx):
    if ctx.invoked_subcommand is None:
        click.echo("Hello {}".format(os.environ.get("USER", "")))
        click.echo("Welcome to Kirsche. Use kirsche --help for help.")
    else:
        pass


@kirsche.command()
@click.option("--paper_id", "-p", help="Paper ID", multiple=True)
@click.option("--source_bib_file", "-sb", type=click.Path(exists=True), help="Bib file path")
@click.option("--target_metadata_path", "-tm", help="Target data file path")
@click.option("--sleep_time", "-st", default=1, help="Sleep time between requests")
def metadata(paper_id, source_bib_file, target_metadata_path, sleep_time):
    """Download paper data from service provides (e.g., SemanticScholar).

    There are two ways to provide a list of DOIs to be retrieved, provide paper DOIs directly using `--paper_id` or `-p`, or loading a bib file using `--source_bib_file` or `-sb`.

    To save the downloaded data, provide a path to a file using `--target_metadata_path` or `-tm`.

    :param paper_id: Paper DOI, optional, can be multiple
    :type paper_id: Union[str, list]
    :param source_bib_file: Bib file path, optional
    :type source_bib_file: str
    :param target_metadata_path: Target data file path, optional
    :type target_metadata_path: str
    :param sleep_time: Sleep time between requests, defaults to 1sec.
    :type sleep_time: Optional[int]
    """
    records = _metadata(paper_id, source_bib_file, target_metadata_path, sleep_time)

    return records


@kirsche.command()
@click.option(
    "--source_metadata_path",
    "-sm",
    type=click.Path(exists=True),
    help="path to data file/folder with paper metadata",
)
@click.option("--connected_papers_path", "-c", help="path to save enhanced data file(s)")
def connections_from_metadata(source_metadata_path, connected_papers_path):
    """Establish connections between the list of papers

    :param source_metadata_path: path to data file with paper metadata
    :type source_metadata_path: str
    :param connected_papers_path: path to save enhanced data file
    :type connected_papers_path: str
    """

    connected_papers = append_connections_for_file(source_metadata_path, connected_papers_path)

    return connected_papers


@kirsche.command()
@click.option("--paper_id", "-p", help="Paper ID", multiple=True)
@click.option("--source_bib_file", "-sb", type=click.Path(exists=True), help="Bib file path")
@click.option(
    "--source_metadata_path",
    "-sm",
    type=click.Path(exists=True),
    help="path to data file/folder with paper metadata",
)
@click.option("--connected_papers_path", "-c", help="path to save enhanced data file")
@click.option("--sleep_time", "-st", default=1, help="Sleep time between requests")
def connections(paper_id, source_bib_file, source_metadata_path, connected_papers_path, sleep_time):
    """Establish connections between the list of papers, either from a list of DOIs, bib file, or from download metadata file.

    If no `metadata_file` provided, the metadata will be downloaded using parameters specified in `paper_id` or `bib_file`.
    If `metadata_file` is provided, the connections will be established using the metadata file.

    ## About Metadata Sources

    Download paper data from service provides (e.g., SemanticScholar).

    There are two ways to provide a list of DOIs to be retrieved, provide paper DOIs directly using `--paper_id` or `-p`, or loading a bib file using `--source_bib_file` or `-sb`.

    To save the downloaded data, provide a path to a file using `--target` or `-t`.


    :param paper_id: Paper DOI, optional, can be multiple
    :type paper_id: str
    :param source_bib_file: Bib file path, optional
    :type source_bib_file: str
    :param source_metadata_path: Target data file path, optional
    :type source_metadata_path: str
    :param connected_papers_path: path to save enhanced data file with connections calcualted
    :type connected_papers_path: Union[str, Path]
    :param sleep_time: Sleep time between requests, defaults to 1sec.
    :type sleep_time: int
    """
    if isinstance(connected_papers_path, str):
        connected_papers_path = Path(connected_papers_path)

    click.secho(f"Retrieving paper metadata...")
    if not source_metadata_path:
        if source_bib_file:
            logger.debug(f"Using bib file: {source_bib_file}")

        if connected_papers_path.exists():
            existing_connected_papers = load_batch_json(connected_papers_path)
        else:
            existing_connected_papers = []

        records = _metadata(paper_id, source_bib_file, None, sleep_time, existing_records=existing_connected_papers)
    else:
        records = load_batch_json(source_metadata_path)
    click.secho(f"  Retrieved {len(records)} records.")

    click.secho(f"Connecting papers...")
    connected_papers = append_connections(records)
    click.secho(f"  Connected papers...")

    # Filter out unnecessary keys in the dictionary
    click.secho(f"Filtering and saving data...")
    connected_papers = save_connected_papers(
        connected_papers, target=connected_papers_path
    )
    click.secho(f"  Done...")

    if not connected_papers_path:
        click.secho(f"No saving path specified, printing simplified data view...")
        dv = DataViews(connected_papers)
        click.echo(dv.json_simple)


@kirsche.command()
@click.option(
    "--source_paper_id", "-sp", required=False, help="Source: Paper ID", multiple=True
)
@click.option(
    "--source_bib_file",
    "-sb",
    required=False,
    type=click.Path(exists=True),
    help="Source: Bib file path",
)
@click.option(
    "--source_metadata_path",
    "-sm",
    required=False,
    type=click.Path(exists=True),
    help="Source: path to data file/folder with paper metadata",
)
@click.option(
    "--source_connected_papers_path",
    "-sc",
    required=False,
    help="Source: path to save enhanced data file/folder",
)
@click.option("--title", default="Kirsche: Paper Graph", help="title of the chart")
@click.option(
    "--target_html_path", "-th", required=True, help="Target: path to html file"
)
@click.option("--sleep_time", "-st", default=1, help="Sleep time between requests")
def visualization(
    source_paper_id,
    source_bib_file,
    source_metadata_path,
    source_connected_papers_path,
    title,
    target_html_path,
    sleep_time,
):
    """ """
    if source_connected_papers_path:
        connected_papers = load_batch_json(source_connected_papers_path)
    else:
        click.secho(f"Retrieving paper metadata...")
        if not source_metadata_path:
            if source_bib_file:
                logger.debug(f"Using bib file: {source_bib_file}")
            records = _metadata(source_paper_id, source_bib_file, None, sleep_time)
        else:
            records = load_batch_json(source_metadata_path)
        click.secho(f"  Retrieved {len(records)} records.")

        click.secho(f"Connecting papers...")
        connected_papers = append_connections(records)
        click.secho(f"  Connected papers...")

        # Filter out unnecessary keys in the dictionary
        click.secho(f"Filtering and saving data...")
        connected_papers = save_connected_papers(connected_papers)
        click.secho(f"  Done...")

    g = PaperGraph(connected_papers, title=title)
    nodes = g.nodes
    edges = g.edges

    click.secho(f"Saving html file...")
    visualize(nodes, edges, g.title, target_html_path)


if __name__ == "__main__":
    pass
