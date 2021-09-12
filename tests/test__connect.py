from loguru import logger
from kirsche.connect import append_connections, append_connections_for_file


def test__connect():
    data_file = "tests/data/io/test__connection.json"
    data = append_connections_for_file(data_file)

    if not data:
        logger.error("Could not connect the papers in the metadata json file")
        assert False
    elif len(data) != 2:
        logger.error("The number of papers in the metadata json file is not correct")
        assert False
    else:
        if not data[0]["local__referenced_to"]:
            logger.error("The local__referenced_to of the first paper is empty")
            assert False
        assert True
