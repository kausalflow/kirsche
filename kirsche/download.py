import json
import time
from pathlib import Path
from typing import Optional, Union

import click
from loguru import logger

from kirsche.utils.bib import get_unique_ids_from_bib
from kirsche.utils.semanticscholar import get_paper_info


def list_dois(
    paper_ids: Optional[Union[list, str]] = None,
    bib_file: Optional[Union[str, Path]] = None,
) -> list:
    """
    list_dois loads a list of DOIs from multiple possible sources

    :param paper_ids: list of DOIs
    :param bib_file: path to bib file
    :return: list of DOIs loaded
    """
    if paper_ids:
        logger.debug(f"Using paper_ids directly...")
        if isinstance(paper_ids, str):
            dois = [paper_ids]
        else:
            dois = paper_ids
    elif bib_file:
        dois = get_unique_ids_from_bib(bib_file)
        logger.debug(f"Retrieved {len(dois)} from {bib_file}")
    else:
        logger.error(f"Specify one of the DOI sources...")
        dois = []

    logger.debug(f"{(len(dois))} DOIs: {dois}")

    return dois


def list_unique_ids(bib_file: Union[str, Path]) -> list:
    """
    list_unique_ids loads a list of unique ids from multiple possible sources

    :param bib_file: path to bib file
    :return: list of unique ids loaded
    """

    unique_ids = get_unique_ids_from_bib(bib_file)
    logger.debug(f"Retrieved {len(unique_ids)} from {bib_file}")

    logger.debug(f"{(len(unique_ids))} unique ids: {unique_ids}")

    return unique_ids


def download_metadata(
    unique_ids: list, target: Optional[Union[str, Path]] = None, sleep_time: int = 1
):
    """Download paper data

    :param unique_ids: list of unique ids to find paper metadata
    :param target: path to save data
    :param sleep_time: time to sleep between requests, defaults to 1
    """

    paper_info = []
    for doi in unique_ids:
        logger.debug(f"Getting info for {doi}")
        paper_info.append(get_paper_info(doi))

        time.sleep(sleep_time)

    if target:
        logger.debug(f"Saving to {target}")
        with open(target, "w") as f:
            json.dump(paper_info, f, indent=4)
        logger.debug(f"Saved to {target}")

    return paper_info


@click.command()
@click.option("--paper_id", "-p", help="Paper ID", multiple=True)
@click.option("--bib_file", "-b", help="Bib file path")
@click.option("--target", "-t", help="Target data file path")
@click.option("--sleep_time", "-s", default=1, help="Sleep time between requests")
def main(paper_id, bib_file, target, sleep_time):
    """Download paper data from service provides (e.g., SemanticScholar)"""

    if bib_file:
        paper_id = list_unique_ids(bib_file)
    elif isinstance(paper_id, str):
        paper_id = [paper_id]

    paper_info = download_metadata(paper_id, target, sleep_time)

    return paper_info


if __name__ == "__main__":
    main()
