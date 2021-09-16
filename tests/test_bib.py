from loguru import logger
from kirsche.utils.bib import load_bib
from kirsche.utils.bib import get_dois_from_bib_re
from kirsche.utils.bib import get_unique_ids_from_bib


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


def test__get_unique_ids_from_bib_pass():
    unique_ids = get_unique_ids_from_bib("tests/data/bib/test.bib")


def test__get_unique_ids_from_bib_content_by_doi():
    unique_ids = get_unique_ids_from_bib("tests/data/bib/test.bib")
    if not unique_ids:
        logger.error(f"Did not load anything from file")
        assert False
    else:
        assert len(unique_ids) == 32


def test__get_unique_ids_from_bib_content_by_arxivid():
    unique_ids = get_unique_ids_from_bib(
        "tests/data/bib/test_arxivid.bib", keys="arxivid"
    )
    if not unique_ids:
        logger.error(f"Did not load anything from file")
        assert False
    elif len(unique_ids) != 9:
        logger.error(f"Total number of records is not right: {len(unique_ids)}")
        assert False
    elif len([i for i in unique_ids if i.startswith("arXiv:")]) != 6:
        logger.error(
            f'Total number of arxiv ids are not right: {len([i for i in unique_ids if i.startswith("arXiv:")])}'
        )
        assert False
    else:
        assert True
