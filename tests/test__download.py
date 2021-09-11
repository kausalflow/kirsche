from kirsche.download import download


def test__download__paper_id():

    paper_id = "10.1038/nrn3241"
    paper_info = download(paper_id, bib_file=None, target=None, sleep_time=1)

    if not paper_info:
        assert False


def test__download__bib():

    bib_file = "tests/data/bib/test__connection.bib"
    paper_info = download(paper_id=None, bib_file=bib_file, target=None, sleep_time=1)

    if not paper_info:
        assert False
    else:
        assert len(paper_info) == 2
