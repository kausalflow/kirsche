from kirsche.utils.semanticscholar import get_paper_info
from loguru import logger


def test_get_paper_info():
    paper = get_paper_info("10.1038/nrn3241")


def test_get_paper_info_content():
    paper = get_paper_info("10.1038/nrn3241")

    if not paper:
        logger.error("No paper found")
        assert False
