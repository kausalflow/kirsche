import json
from pathlib import Path
from typing import Optional, Union

import click
from loguru import logger

from kirsche.utils.io import load_json, save_json, save_batch_json
from kirsche.utils.constants import UNIQUE_ID_PRECEDENCE


def append_connections(
    papers: list, connection_field_name: Optional[str] = "local__referenced_to"
) -> list:
    """find connections between papers based on citation doi

    :param papers: list of paper metadata
    :param connection_field_name: name of the field to save the connection info
    :return: list of paper metadata with connection info
    """

    if connection_field_name is None:
        connection_field_name = "local__referenced_to"

    logger.debug(f"Appending connections to {len(papers)} papers...")

    enhanced_papers = []

    for ps in papers:
        # Convert doi to lower case
        ps_doi = ps.get("doi", "")
        if not ps_doi:
            ps_doi = ""
        ps_doi = ps_doi.lower()
        ps["doi"] = ps_doi

        # find references that are in the current papers list
        ps_references = ps["references"]
        ps_reference_dois = [
            psr.get("doi", "").lower() for psr in ps_references if psr.get("doi")
        ]
        ps_referenced_to = []
        for pt in papers:
            pt_doi = pt.get("doi", "")
            if not pt_doi:
                pt_doi = ""
            else:
                pt_doi = pt_doi.lower()
            if pt_doi in ps_reference_dois:
                ps_referenced_to.append(pt_doi)

        ps[connection_field_name] = ps_referenced_to
        enhanced_papers.append(ps)

    logger.debug(
        f"enhanced {len([p for p in enhanced_papers if p.get(connection_field_name)])}"
    )

    return enhanced_papers


def save_connected_papers(
    records: list,
    target: Optional[Union[str, Path]] = None,
    save_keys: Optional[list] = None,
    connection_field_name: Optional[str] = "local__referenced_to",
):

    if connection_field_name is None:
        connection_field_name = "local__referenced_to"

    if save_keys is None:
        save_keys = [
            "corpusId",
            "title",
            "authors",
            "doi",
            "venue",
            "numCitedBy",
            "numCiting",
            "year",
            connection_field_name,
        ] + UNIQUE_ID_PRECEDENCE
        save_keys = list(set(save_keys))
        logger.debug(f"Saving only {save_keys} keys from the original paper metadata")

    records = [{k: v for k, v in p.items() if k in save_keys} for p in records]

    if target:
        logger.debug(f"Saving connected papers to {target}")
        save_batch_json(records, target)

    return records


def append_connections_for_file(
    data_file: Union[str, Path],
    target: Optional[Union[str, Path]] = None,
    save_keys: Optional[list] = None,
    connection_field_name: Optional[str] = "local__referenced_to",
):
    """connect papers based on citation doi

    :param data_file: path to json file that contains the downloaded paper metadata
    :param target: path to json file to save the enhanced paper metadata
    :param save_keys: list of keys to save from the original paper metadata
    :param connection_field_name: name of the field to save the connection info
    :return: list of paper metadata with connection info
    """

    if connection_field_name is None:
        connection_field_name = "local__referenced_to"

    papers = load_json(data_file)

    c_p = append_connections(papers, connection_field_name=connection_field_name)

    # Filter out unnecessary keys in the dictionary
    c_p = save_connected_papers(
        c_p,
        target=target,
        save_keys=save_keys,
        connection_field_name=connection_field_name,
    )

    return c_p


@click.command()
@click.option("--data_file", "-d", help="path to data file with paper metadata")
@click.option("--target", "-t", help="path to save enhanced data file")
def main(data_file, target):

    append_connections_for_file(data_file, target)


if __name__ == "__main__":
    main()
