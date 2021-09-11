from lychee.utils.semanticscholar import get_paper_info
from loguru import logger


def test__get_paper_info():
    paper = get_paper_info("10.1038/nrn3241")


def test__get_paper_info__content():
    paper = get_paper_info("10.1038/nrn3241")

    if not paper:
        logger.error("No paper found")
        assert False
