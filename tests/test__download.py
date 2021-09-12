from kirsche.download import download_metadata
from kirsche.download import list_dois


def test__download__paper_id():

    paper_id = "10.1038/nrn3241"
    paper_info = download_metadata([paper_id], target=None, sleep_time=1)

    if not paper_info:
        assert False


def test__download__bib():

    bib_file = "tests/data/bib/test__connection.bib"
    dois = list_dois(None, bib_file)
    paper_info = download_metadata(
        dois, target=None, sleep_time=1
    )

    if not paper_info:
        assert False
    else:
        assert len(paper_info) == 2
