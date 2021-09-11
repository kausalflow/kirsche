from loguru import logger
import click
import json


def load_data(data_file):
    """load data from json file"""

    logger.debug(f"loading data from {data_file}")
    with open(data_file, "r") as f:
        data = json.load(f)

    logger.debug(f"loaded {len(data)} papers")
    return data


def connect_papers(papers):
    """find connections between papers based on citation doi"""

    enhanced_papers = []

    for ps in papers:
        ps_references = ps["references"]
        ps_reference_dois = [psr["doi"] for psr in ps_references]
        ps_connected_to = []
        for pt in papers:
            pt_doi = pt["doi"]
            if pt_doi in ps_reference_dois:
                ps_connected_to.append(pt_doi)

        ps["connected_to"] = ps_connected_to
        enhanced_papers.append(ps)

    return enhanced_papers


@click.command()
@click.option("--data_file")
@click.option("--target")
def main(data_file, target):

    save_keys = [
        "title",
        "authors",
        "doi",
        "venue",
        "numCitedBy",
        "numCiting",
        "year",
        "connected_to",
    ]

    papers = load_data(data_file)

    c_p = connect_papers(papers)

    c_p = [{k: v for k, v in p.items() if k in save_keys} for p in c_p]

    with open(target, "w") as f:
        json.dump(c_p, f, indent=4)


if __name__ == "__main__":
    main()
