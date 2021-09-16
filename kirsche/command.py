import os
import sys

import click
from loguru import logger
from kirsche.download import list_unique_ids, download_metadata
from kirsche.connect import (
    append_connections,
    append_connections_for_file,
    save_connected_papers,
)
from kirsche.dataset import DataViews
from kirsche.utils.io import load_json
from kirsche.utils.bib import load_bib


logger.remove()
logger.add(sys.stderr, level="INFO", enqueue=True)


__CWD__ = os.getcwd()


def _metadata(paper_id, bib_file, metadata_file, sleep_time):
    """Download paper data from service provides (e.g., SemanticScholar).

    There are two ways to provide a list of unique ids to be retrieved, provide paper DOIs directly using `--paper_id` or `-p`, or loading a bib file using `--bib_file` or `-b`.

    To save the downloaded data, provide a path to a file using `--target` or `-t`.

    :param paper_id: Paper unique ids, optional, can be multiple
    :type paper_id: str
    :param bib_file: Bib file path, optional
    :type bib_file: str
    :param metadata_file: Target data file path, optional
    :type metadata_file: str
    :param sleep_time: Sleep time between requests, defaults to 1sec.
    :type sleep_time: int
    """

    click.echo(f"Retrieving unique ids...")
    logger.debug(f"loading bib {bib_file}")
    bib_content = load_bib(bib_file)
    logger.debug(f"bib {bib_file} content: {bib_content}")
    if bib_file:
        paper_id = list_unique_ids(bib_file)
    elif isinstance(paper_id, str):
        paper_id = [paper_id]

    click.echo(f"  Retrieved {len(paper_id)} unique ids")

    if not paper_id:
        click.secho(
            "No unique ids input. Specify unique ids using `-p` or a bib file using `-b`", fg="red"
        )

    paper_info = download_metadata(paper_id, metadata_file, sleep_time)

    if not metadata_file:
        dv = DataViews(paper_info)
        click.echo(dv.json_simple)

    return paper_info


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
@click.option("--bib_file", "-b", type=click.Path(exists=True), help="Bib file path")
@click.option("--metadata_file", "-m", help="Target data file path")
@click.option("--sleep_time", "-s", default=1, help="Sleep time between requests")
def metadata(paper_id, bib_file, metadata_file, sleep_time):
    """Download paper data from service provides (e.g., SemanticScholar).

    There are two ways to provide a list of DOIs to be retrieved, provide paper DOIs directly using `--paper_id` or `-p`, or loading a bib file using `--bib_file` or `-b`.

    To save the downloaded data, provide a path to a file using `--target` or `-t`.

    :param paper_id: Paper DOI, optional, can be multiple
    :type paper_id: str
    :param bib_file: Bib file path, optional
    :type bib_file: str
    :param metadata_file: Target data file path, optional
    :type metadata_file: str
    :param sleep_time: Sleep time between requests, defaults to 1sec.
    :type sleep_time: int
    """
    records = _metadata(paper_id, bib_file, metadata_file, sleep_time)

    return records


@kirsche.command()
@click.option(
    "--metadata_file",
    "-m",
    type=click.Path(exists=True),
    help="path to data file with paper metadata",
)
@click.option("--connected_papers_file", "-c", help="path to save enhanced data file")
def connections_from_metadata(metadata_file, connected_papers_file):
    """Establish connections between the list of papers

    :param metadata_file: path to data file with paper metadata
    :type metadata_file: str
    :param connected_papers_file: path to save enhanced data file
    :type connected_papers_file: str
    """

    connected_papers = append_connections_for_file(metadata_file, connected_papers_file)

    return connected_papers


@kirsche.command()
@click.option("--paper_id", "-p", help="Paper ID", multiple=True)
@click.option("--bib_file", "-b", type=click.Path(exists=True), help="Bib file path")
@click.option(
    "--metadata_file",
    "-m",
    type=click.Path(exists=True),
    help="path to data file with paper metadata",
)
@click.option("--connected_papers_file", "-c", help="path to save enhanced data file")
@click.option("--sleep_time", "-s", default=1, help="Sleep time between requests")
def connections(paper_id, bib_file, metadata_file, connected_papers_file, sleep_time):
    """Establish connections between the list of papers, either from a list of DOIs, bib file, or from download metadata file.

    If no `metadata_file` provided, the metadata will be downloaded using parameters specified in `paper_id` or `bib_file`.
    If `metadata_file` is provided, the connections will be established using the metadata file.

    ## About Metadata Sources

    Download paper data from service provides (e.g., SemanticScholar).

    There are two ways to provide a list of DOIs to be retrieved, provide paper DOIs directly using `--paper_id` or `-p`, or loading a bib file using `--bib_file` or `-b`.

    To save the downloaded data, provide a path to a file using `--target` or `-t`.


    :param paper_id: Paper DOI, optional, can be multiple
    :type paper_id: str
    :param bib_file: Bib file path, optional
    :type bib_file: str
    :param metadata_file: Target data file path, optional
    :type metadata_file: str
    :param connected_papers_file: path to save enhanced data file with connections calcualted
    :type connected_papers_file: str
    :param sleep_time: Sleep time between requests, defaults to 1sec.
    :type sleep_time: int
    """
    click.secho(f"Retrieving paper metadata...")
    if not metadata_file:
        if bib_file:
            logger.debug(f"Using bib file: {bib_file}")
        records = _metadata(paper_id, bib_file, None, sleep_time)
    else:
        records = load_json(metadata_file)
    click.secho(f"  Retrieved {len(records)} records.")

    click.secho(f"Connecting papers...")
    connected_papers = append_connections(records)
    click.secho(f"  Connected papers...")

    # Filter out unnecessary keys in the dictionary
    click.secho(f"Filtering and saving data...")
    connected_papers = save_connected_papers(
        connected_papers, target=connected_papers_file
    )
    click.secho(f"  Done...")

    if not connected_papers_file:
        dv = DataViews(connected_papers)
        click.echo(dv.json_simple)


if __name__ == "__main__":
    pass
