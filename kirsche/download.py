import json
import time
from pathlib import Path

import click
from loguru import logger

from kirsche.utils import bib
from kirsche.utils.bib import get_unique_ids_from_bib, load_bib
from kirsche.utils.constants import UNIQUE_ID_PREFIX
from kirsche.utils.semanticscholar import get_paper_info


def list_dois(paper_ids, bib_file):
    """
    list_dois loads a list of DOIs from multiple possible sources

    :param paper_ids: list of DOIs
    :type paper_ids: list
    :param bib_file: path to bib file
    :type bib_file: str
    :return: list of DOIs loaded
    :rtype: list
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


def list_unique_ids(bib_file):
    """
    list_unique_ids loads a list of unique ids from multiple possible sources

    :param bib_file: path to bib file
    :type bib_file: str
    :return: list of unique ids loaded
    :rtype: list
    """

    unique_ids = get_unique_ids_from_bib(bib_file)
    logger.debug(f"Retrieved {len(unique_ids)} from {bib_file}")

    logger.debug(f"{(len(unique_ids))} unique ids: {unique_ids}")

    return unique_ids


def download_metadata(dois, target, sleep_time=1):
    """Download paper data

    :param target: path to save data
    :type target: str
    :param sleep_time: time to sleep between requests, defaults to 1
    :type sleep_time: int
    """

    paper_info = []
    for doi in dois:
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

    dois = list_dois(paper_id, bib_file)

    paper_info = download_metadata(dois, target, sleep_time)

    return paper_info


if __name__ == "__main__":
    main()
