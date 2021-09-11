import json
from loguru import logger
from kirsche.utils.web import get_page_content


def get_paper_info(paper_id, API_BASE=None):
    """
    Get paper info from Semantic Scholar API
    """
    if API_BASE is None:
        API_BASE = "https://api.semanticscholar.org/v1/paper/"

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
