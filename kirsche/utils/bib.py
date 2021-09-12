import re
import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode


def load_bib(bib_file):
    """Load bib content from bib files"""

    with open(bib_file, "r") as bibtex_file:
        parser = BibTexParser(common_strings=True)
        parser.customization = convert_to_unicode
        bib_database = bibtexparser.load(bibtex_file, parser=parser)

    return bib_database.entries


def get_dois_from_bib_re(bib_file):
    """Retrieve DOIs by parsing bib file line by line."""

    with open(bib_file, "r") as bibtex_file:
        data = bibtex_file.readlines()

    re_doi = re.compile(r"^doi\s=\s\{(?P<doi>.+)\}")

    dois = [re_doi.search(i.strip()) for i in data]
    dois = [i.group("doi") for i in dois if i is not None]

    return dois


def get_dois_from_bib(bib_file):
    """
    get_dois_from_bib returns a list of DOIs from a bib file

    :param bib_file: path to bib file
    :type bib_file: str
    :return: list of DOIs
    :rtype: list
    """
    bib_data = load_bib(bib_file)
    dois = [b.get("doi", "").lower() for b in bib_data]

    return dois


if __name__ == "__main__":
    bib_data = load_bib("tests/data/bib/test.bib")

    pass
