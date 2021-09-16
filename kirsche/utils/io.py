import json
from pathlib import Path
from typing import Union

from loguru import logger


def load_json(data_file: Union[str, Path]) -> Union[dict, list]:
    """load data from json file

    :param data_file: json file path
    :type data_file: str
    """
    if isinstance(data_file, str):
        data_file = Path(data_file)
    if not data_file.exists():
        raise Exception(f"File not found: {data_file}")

    logger.debug(f"loading data from {data_file}")
    with open(data_file, "r") as f:
        data = json.load(f)

    logger.debug(f"loaded {len(data)} papers")
    return data
