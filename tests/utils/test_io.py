from kirsche.utils.io import load_json


def test_load_json():
    assert load_json("tests/data/io/test_json.json") == {"test": "test"}
