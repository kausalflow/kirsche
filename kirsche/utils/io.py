import json
from pathlib import Path
from typing import Union, Optional
from kirsche.utils.constants import UNIQUE_ID_PRECEDENCE, UNIQUE_ID_PREFIX

from loguru import logger


def load_json(data_file: Union[str, Path]) -> dict:
    """load dict/list of dict data from json file

    :param data_file: json file path
    """
    if isinstance(data_file, str):
        data_file = Path(data_file)
    if not data_file.exists():
        raise Exception(f"File not found: {data_file}")

    logger.debug(f"loading data from {data_file}")
    with open(data_file, "r") as f:
        data = json.load(f)

    return data.copy()


def is_dir(path: Union[str, Path]) -> bool:
    """Check if the given path is a directory

    :param path: path to be checked
    """
    if isinstance(path, str):
        path = Path(path)

    if path.exists():
        return path.is_dir()
    else:
        return str(path).endswith("/")


def load_batch_json(data_path: Union[str, Path]) -> Union[dict, list]:
    """load data from json file(s)

    If the given `data_path` is a folder, all the json files in the folder are loaded. If the given `data_path` is a single json file, everything inside the file will be loaded.

    :param data_path: json file path
    """
    if isinstance(data_path, str):
        data_path = Path(data_path)

    if not data_path.exists():
        return []

    if data_path.is_dir():
        logger.debug(f"loading all data files from {data_path} folder")
        data_path_all_json = list(data_path.glob("*.json"))
        logger.debug(f"Found {len(data_path_all_json)} json files in {data_path}.")
        data = []
        for data_file in data_path_all_json:
            logger.debug(f"loading data from {data_file}")
            data.append(load_json(data_file))
    elif data_path.is_file():
        logger.debug(f"loading data from a single file {data_path}")
        data = load_json(data_path)

    return data


def save_json(data: Union[dict, list], data_file: Union[str, Path]) -> None:
    """save data to json file

    !!! warning "This Function Overwrites any Existing Content"
        Beware that all contents in the file will be overwritten if it exists.

    :param data: dictionary data to be saved
    :param data_file: json file path
    """
    if isinstance(data_file, str):
        data_file = Path(data_file)
    if data_file.exists():
        logger.warning(f"{data_file} exists! Will replace the content")

    logger.debug(f"saving data to {data_file}")
    with open(data_file, "w") as f:
        json.dump(data, f, indent=4)


def save_batch_json(
    records: list, data_path: Union[str, Path], unique_key=None,
    mode = None
) -> None:
    """save data to json file.

    There are two modes:
    - single file mode, if the `data_path` is a folder, and
    - multi file mode, if the `data_path` is a json file path.

    In the single file mode, all the entries in the data are saved to the same file. In the multi file mode, each entry will be saved as a separate file.

    Single file mode is good for long term presevation, and multi file mode is good for updates.

    :param records: list of data to be saved
    :param data_path: json file path or folder path
    """
    if isinstance(data_path, str):
        data_path = Path(data_path)

    if not data_path.exists():
        if str(data_path).endswith(".json"):
            mode = "single"
        else:
            mode = "multi"

    if unique_key is None:
        unique_key = "corpusId"

    if data_path.is_dir() or (mode == "multi"):
        if not data_path.exists():
            data_path.mkdir(parents=True)
        logger.debug(f"saving all data records to {data_path} folder")
        data_path_all_json = list(data_path.glob("*.json"))
        logger.debug(f"Found {len(data_path_all_json)} json files in {data_path}.")
        data = []
        for record in records:
            # Construct path
            try:
                unique_key_value = record[unique_key]
            except KeyError:
                logger.error(f"{unique_key} not found in {record}")
                continue

            data_file = data_path / f"{unique_key_value}.json"
            logger.debug(f"saving data to {data_file}")
            save_json(record, data_file)

    else:
        logger.debug(f"loading data from a single file {data_path}")
        save_json(records, data_path)



def record_exists(
    id,
    existing_records: list,
    keys: list = UNIQUE_ID_PRECEDENCE,
    unique_id_prefix: list = UNIQUE_ID_PREFIX,
) -> bool:
    """Whether the record already exists in the data file

    :param data_path: json files folder path
    """

    if keys is None:
        keys = UNIQUE_ID_PRECEDENCE
    if unique_id_prefix is None:
        unique_id_prefix = UNIQUE_ID_PREFIX

    # The keys are most likely to have prefixes, e.g., arXiv:, PMID:
    # we need to strip them out before checking if the record exists
    cleansing_id = id
    for k, v in unique_id_prefix.items():
        if id.startswith(v):
            cleansing_id = id.replace(v, "")
            break

    # set default value to False as this is more acceptable in most cases
    # if we missed something in the lookup, we will redownload the data
    # if we use False as default. This is no big deal.
    # Otherwise, we might miss some data.
    exists = False

    for record in existing_records:
        for k in keys:
            k_value = record.get(k, "")
            if k_value.lower() == cleansing_id.lower():
                return True

    return exists


if __name__ == "__main__":

    test_path = "tests/data/io/test__metadata"
    existing_metadata = load_batch_json(test_path)

    print(existing_metadata[0]["doi"])

    print(
        [
            record_exists(i["doi"], existing_metadata) for i in existing_metadata
        ]
    )

    pass