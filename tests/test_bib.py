from loguru import logger
from lychee.utils.bib import load_bib
from lychee.utils.bib import get_dois_from_bib_re


def test__load_bib():
    bib_data = load_bib("tests/data/bib/test.bib")


def test__load_bib__has_content():
    bib_data = load_bib("tests/data/bib/test.bib")
    if not bib_data:
        logger.error(f"Did not load anything from file")
        assert False
    else:
        assert len(bib_data) == 32


def test__get_dois_from_bib_re():
    dois = get_dois_from_bib_re("tests/data/bib/test.bib")


def test__get_dois_from_bib_re__has_content():
    dois = get_dois_from_bib_re("tests/data/bib/test.bib")
    if not dois:
        logger.error(f"Did not load anything from file")
        assert False
    else:
        assert len(dois) == 32
