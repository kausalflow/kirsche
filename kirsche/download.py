import click
import json
from loguru import logger
import time
from kirsche.utils.semanticscholar import get_paper_info
from kirsche.utils.bib import load_bib


def get_dois(bib_file):
    """
    get_dois returns a list of DOIs from a bib file

    :param bib_file: path to bib file
    :type bib_file: str
    :return: list of DOIs
    :rtype: list
    """
    bib_data = load_bib(bib_file)
    dois = [b.get("doi", "").lower() for b in bib_data]

    return dois


def download(paper_id, bib_file, target, sleep_time):
    """Download paper data"""

    if paper_id is not None:
        if isinstance(paper_id, str):
            paper_id = [paper_id]
    else:
        paper_id = get_dois(bib_file)
        logger.debug(paper_id)

    paper_info = []
    for doi in paper_id:
        logger.info(f"Getting info for {doi}")
        paper_info.append(get_paper_info(doi))
        # logger.debug(paper_info)

        time.sleep(sleep_time)

    if target:
        logger.info(f"Saving to {target}")
        with open(target, "w") as f:
            json.dump(paper_info, f, indent=4)
        logger.info(f"Saved to {target}")

    # logger.debug(json.dumps(paper_info, indent=4))

    return paper_info


@click.command()
@click.option("--paper_id", "-p", help="Paper ID", multiple=True)
@click.option("--bib_file", "-b", help="Bib file path")
@click.option("--target", "-t", help="Target data file path")
@click.option("--sleep_time", "-s", default=1, help="Sleep time between requests")
def main(paper_id, bib_file, target, sleep_time):
    """Download paper data from service provides (e.g., SemanticScholar)"""

    paper_info = download(paper_id, bib_file, target, sleep_time)

    return paper_info


if __name__ == "__main__":
    main()
