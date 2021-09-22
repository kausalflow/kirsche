import re
from pathlib import Path
from typing import Optional, Union

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
from kirsche.utils.constants import UNIQUE_ID_PRECEDENCE, UNIQUE_ID_PREFIX


def load_bib(bib_file: Union[str, Path]) -> list:
    """Load bib content from bib files"""

    if isinstance(bib_file, str):
        bib_file = Path(bib_file)

    if not bib_file.exists():
        raise FileNotFoundError(f"{bib_file} does not exist")

    with open(bib_file, "r") as bibtex_file:
        parser = BibTexParser(common_strings=True)
        parser.customization = convert_to_unicode
        bib_database = bibtexparser.load(bibtex_file, parser=parser)

    return bib_database.entries


def get_dois_from_bib_re(bib_file: Union[str, Path]) -> list:
    """Retrieve DOIs by parsing bib file line by line."""

    with open(bib_file, "r") as bibtex_file:
        data = bibtex_file.readlines()

    re_doi = re.compile(r"^doi\s=\s\{(?P<doi>.+)\}")

    dois = [re_doi.search(i.strip()) for i in data]
    dois = [i.group("doi") for i in dois if i is not None]

    return dois


def parse_unique_ids_by_keys(
    bib_data: list, keys: Union[str, list], unique_id_prefix: dict
) -> list:
    """
    parse_unique_ids_by_keys parses bib data based on keys.

    :param bib_data: list of bib records loaded from a bib file
    :param keys: list of keys as the lookup order, e.g., ["doi", "arxivid", "pmid"]
    :param unique_id_prefix: a dictionary to specify what prefix to use for each key
    """

    ids = []
    for i in bib_data:
        i_unique_id = ""
        for k in keys:
            k_prefix = unique_id_prefix.get(k, "")
            i_k_value = i.get(k, "")
            # We do not need the version in the arxivids
            if k == "arxivid":
                i_k_value = i_k_value.split("v")[0]
            if i_k_value:
                i_unique_id = f"{k_prefix}{i_k_value}"
                break
        ids.append(i_unique_id)

    return ids


def get_unique_ids_from_bib(
    bib_file: Union[str, Path],
    keys: Optional[Union[str, list]] = None,
    unique_id_prefix: dict = None,
) -> list:
    """
    get_unique_ids_from_bib returns a list of unique IDs from a bib file for a given key or list of keys.

    By default, the key is "doi". It can also be
    - arxivid, which can return values like arXiv:0804.4726
    - pmid, which can return values like PMID:26017442.

    keys can also be a list of keys to check in order of priority, e.g., `["doi", "arxivid", "pmid"]`.

    For each record, we will look up the paper based on the order of the list. If doi exists, the functioin will use doi and start the next record. If doi is not found, the function will use arxivid for the same record.

    If only one value in keys is specified, we will the same key specified for all records.

    :param bib_file: path to bib file
    :type bib_file: str
    :param keys: key to use to find unique ids in the bib data, default is doi.
    :type keys:
    :param unique_id_prefix: prefix to use for unique ids
    :type unique_id_prefix: str
    :return: list of DOIs
    :rtype: list
    """
    if keys is None:
        keys = UNIQUE_ID_PRECEDENCE
    elif isinstance(keys, str):
        keys = [keys]

    if unique_id_prefix is None:
        unique_id_prefix = UNIQUE_ID_PREFIX

    bib_data = load_bib(bib_file)

    if keys:
        ids = parse_unique_ids_by_keys(bib_data, keys, unique_id_prefix)
    else:
        raise ValueError("key or key_precedence must be specified")

    return ids


def get_dois_from_bib(bib_file: Union[str, Path]) -> list:
    """
    [Deprecated] use get_unique_ids_from_bib instead.

    get_dois_from_bib returns a list of DOIs from a bib file

    :param bib_file: path to bib file
    :type bib_file: str
    :return: list of DOIs
    :rtype: list
    """

    return get_unique_ids_from_bib(bib_file, key="doi")


if __name__ == "__main__":
    bib_data = load_bib("tests/data/bib/test_small.bib")

    unique_ids = get_unique_ids_from_bib(
        "tests/data/bib/test_arxivid.bib", keys="arxivid"
    )

    from kirsche.utils.constants import UNIQUE_ID_PRECEDENCE

    unique_ids_by_precedence = get_unique_ids_from_bib(
        "tests/data/bib/test_arxivid.bib", keys=UNIQUE_ID_PRECEDENCE
    )

    pass
