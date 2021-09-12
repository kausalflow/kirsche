import json

import click
from loguru import logger

from kirsche.utils.io import load_json


def append_connections(papers, connection_field_name=None):
    """find connections between papers based on citation doi

    :param papers: list of paper metadata
    :type papers: list
    :return: list of paper metadata with connection info
    :rtype: list
    """

    if connection_field_name is None:
        connection_field_name = "local__referenced_to"

    logger.debug(f"Appending connections to {len(papers)} papers...")

    enhanced_papers = []

    for ps in papers:
        ps_references = ps["references"]
        ps_reference_dois = [
            psr.get("doi", "").lower() for psr in ps_references if psr.get("doi")
        ]
        ps_referenced_to = []
        for pt in papers:
            pt_doi = pt.get("doi", "").lower()
            if pt_doi in ps_reference_dois:
                ps_referenced_to.append(pt_doi)

        ps[connection_field_name] = ps_referenced_to
        enhanced_papers.append(ps)

    logger.debug(
        f"enhanced {len([p for p in enhanced_papers if p.get(connection_field_name)])}"
    )

    return enhanced_papers


def append_connections(
    data_file, target=None, save_keys=None, connection_field_name=None
):
    """connect papers based on citation doi

    :param data_file: path to json file that contains the downloaded paper metadata
    :type data_file: str
    :param target: path to json file to save the enhanced paper metadata
    :type target: str
    :param save_keys: list of keys to save from the original paper metadata
    :type save_keys: list
    :param connection_field_name: name of the field to save the connection info
    :type connection_field_name: str
    :return: list of paper metadata with connection info
    :rtype: list
    """

    if connection_field_name is None:
        connection_field_name = "local__referenced_to"

    if save_keys is None:
        save_keys = [
            "title",
            "authors",
            "doi",
            "venue",
            "numCitedBy",
            "numCiting",
            "year",
            connection_field_name,
        ]

    papers = load_json(data_file)

    c_p = append_connections(papers, connection_field_name=connection_field_name)

    c_p = [{k: v for k, v in p.items() if k in save_keys} for p in c_p]

    if target:
        with open(target, "w") as f:
            json.dump(c_p, f, indent=4)

    return c_p


@click.command()
@click.option("--data_file", "-d", help="path to data file with paper metadata")
@click.option("--target", "-t", help="path to save enhanced data file")
def main(data_file, target):

    append_connections(data_file, target)


if __name__ == "__main__":
    main()
