from loguru import logger
from json import load
from kirsche.dataset import Dataset
from kirsche.dataset import DataViews
from kirsche.utils.io import load_json


def test__DataViews():
    data_file = "tests/data/io/test__connection_enhanced.json"
    data = load_json(data_file)
    dv = DataViews(data)

    dv_json_simple = dv.json_simple

    if not dv_json_simple:
        logger.error(f"JSON simple view of data is not working")
        assert False


def test__Dataset():
    paper_file = "tests/data/io/test__connection.json"
    extra_data_file = "tests/data/io/test__connection_extra_labels.json"
    papers = load_json(paper_file)
    extra_data = load_json(extra_data_file)

    additional_keys = [
        {
            "key": "label_group_a",
        }
    ]

    for add_keys in [None, additional_keys]:
        logger.debug(f"Testing with additional_keys: {add_keys}...")

        ds = Dataset(papers, extra_data, additional_keys=add_keys)

        ds_connections = ds.connections("year", "numCitedBy")
        ds_papers = ds.papers
        logger.debug(f"There are {len(ds_papers)} papers in the dataset")

        if not ds_papers:
            logger.error(f"Dataset papers property is not right")
            assert False

        if not ds_connections:
            logger.error(f"Dataset connections calculation is not right")
            assert False
