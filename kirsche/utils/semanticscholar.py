import json

from loguru import logger

from kirsche.utils.web import get_page_content

GRAPH_API = "https://api.semanticscholar.org/graph/v1/paper/"
FIELDS = ",".join(
    [
        "paperId",
        "corpusId",
        "url",
        "title",
        "abstract",
        "venue",
        "year",
        "authors",
        "externalIds",
        "citationCount",
        "referenceCount",
        "influentialCitationCount",
        "isOpenAccess",
        "fieldsOfStudy",
        "references.paperId",
        "references.title",
        "references.year",
        "references.venue",
        "references.externalIds",
    ]
)


def _paper_ref(paper_id: str) -> str:
    """Semantic Scholar's Graph API wants a prefix on DOIs (``DOI:10.x/...``)."""
    if paper_id.lower().startswith("10."):
        return f"DOI:{paper_id}"
    return paper_id


def _ids(record: dict) -> dict:
    ext = record.get("externalIds") or {}
    return {
        "doi": ext.get("DOI"),
        "arxivId": ext.get("ArXiv"),
        "pmid": ext.get("PubMed"),
    }


def to_v1(record: dict) -> dict:
    """A Graph API record in the shape the retired v1 API returned, which the rest of kirsche reads."""
    out = dict(record)
    out.update(_ids(record))
    out["numCitedBy"] = record.get("citationCount")
    out["numCiting"] = record.get("referenceCount")
    out["references"] = [
        {**r, **_ids(r)} for r in (record.get("references") or []) if r
    ]
    return out


def get_paper_info(paper_id: str, API_BASE=None) -> dict:
    """
    Get paper info from the Semantic Scholar Graph API

    The v1 API kirsche used before is gone; the record is returned in its shape
    (``doi``, ``numCitedBy``, ``numCiting``, ``references[].doi`` ...).

    :param paper_id: a DOI, or an id with a prefix such as ``arXiv:`` or ``PMID:``
    :param API_BASE: base url for the API, default is Semantic Scholar's Graph API
    """
    if API_BASE is None:
        API_BASE = GRAPH_API

    logger.debug(f"Getting paper info using base URL {paper_id}")

    url = f"{API_BASE}{_paper_ref(paper_id)}?fields={FIELDS}"

    test_content = get_page_content(url)

    if test_content["status"] != 200:
        raise Exception(
            f"Error: Semantic Scholar API returned status code {test_content['status']}"
        )
    else:
        paper_info = json.loads(test_content["content"].text)
        return to_v1(paper_info)
