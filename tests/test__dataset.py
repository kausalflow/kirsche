from loguru import logger
from json import load
from kirsche.dataset import Dataset
from kirsche.dataset import DataViews
from kirsche.utils.io import load_json

def test__DataViews():
    data_file = "tests/data/io/test__connection_enhanced.json"
    data = load_json(data_file)
    dv = DataViews(data)

    dv_json_simple = dv.json_simple()

    if not dv_json_simple:
        logger.error(f"JSON simple view of data is not working")
        assert False


