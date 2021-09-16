import json

from kirsche.utils.web import get_page_content
from loguru import logger


def get_paper_info(paper_id: list, API_BASE=None) -> list:
    """
    Get paper info from Semantic Scholar API

    :param paper_id: list of paper ids
    :param API_BASE: base url for the API, default is semanticscholar
    """
    if API_BASE is None:
        API_BASE = "https://api.semanticscholar.org/v1/paper/"

    logger.debug(f"Getting paper info using base URL {paper_id}")

    # Get paper info from Semantic Scholar API
    url = API_BASE + paper_id

    test_content = get_page_content(url)

    if test_content["status"] != 200:
        raise Exception(
            f"Error: Semantic Scholar API returned status code {test_content['status']}"
        )
    else:
        paper_info = json.loads(test_content["content"].text)
        return paper_info
