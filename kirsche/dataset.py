from loguru import logger
from kirsche.connect import append_connections
import json


class DataViews:
    def __init__(self, data) -> None:
        if not data:
            logger.warning("No data provided!")
            self.data = []
        else:
            self.data = data

    @property
    def json_full(self):
        """JSON representation of the full data"""
        return json.dumps(self.data, indent=4)

    @property
    def json_simple(self):
        """JSON representation of a few selected keys of the data"""

        records = []
        for record in self.data:
            records.append(self._json__simple(record))

        return json.dumps(records, indent=4)

    @staticmethod
    def _json__simple(record, show_keys=None, connection_field_name=None) -> str:
        """Show only some keys of a record"""

        if connection_field_name is None:
            connection_field_name = "local__referenced_to"

        if show_keys is None:
            show_keys = [
                "doi",
                "authors",
                "title",
                "venue",
                "year",
                "numCitedBy",
                "numCiting",
                f"{connection_field_name}_count",
            ]

        if f"{connection_field_name}_count" not in record:
            record[f"{connection_field_name}_count"] = len(
                record.get(connection_field_name, [])
            )

        record = {k: v for k, v in record.items() if k in show_keys}

        return record


def format_authors(paper):
    """
    format_authors formats list of author fields to strings

    :param paper: dict of paper meta data
    :type paper: dict
    :return: string format of authors
    :rtype: str
    """
    authors = paper["authors"]
    if len(authors) > 2:
        author = authors[0]["name"].split(" ")[-1] + " et al."
    elif len(authors) == 2:
        author = (
            authors[0]["name"].split(" ")[-1]
            + " & "
            + authors[-1]["name"].split(" ")[-1]
        )
    else:
        author = authors[0]["name"].split(" ")[-1]

    year = f', {paper["year"]}'

    return author + year


def add_additional_data_to_papers(papers, extra_data, extra_data_use_keys):
    """Enhance paper metadata using extra data

    :param papers: list of paper metadata
    :type papers: list
    :param extra_data: extra data as a dictionary with keys as DOIs
    :type extra_data: dict
    :param extra_data_use_keys: list of keys to use from extra data
    :type extra_data_use_keys: list
    :return: enhanced list of papers
    :rtype: list
    """
    enhanced_papers = []
    for p in papers:
        p_extra_data = extra_data.get(p["doi"].lower(), {})
        if extra_data_use_keys is None:
            extra_data_use_keys = p_extra_data.keys()

        # Take only the required fields and values
        p_extra_data = {
            k: p_extra_data[k] for k in p_extra_data if k in extra_data_use_keys
        }
        p.update(p_extra_data)
        enhanced_papers.append(p)

    return enhanced_papers


class Dataset:
    """
    Dataset to prepare data about papers.

    There are two groups of keys and transformations:
    - `builtin_keys`, and
    - `additional_keys`.

    `builtin_keys` are keys that are always present in the dataset. `additional_keys` are the keys that may appear in the additional data in `labels`.

    `builtin_keys` param is default to

    ```
    builtin_keys = [
        {"key": "authors", "transform": format_authors},
        {"key": "year"},
        {"key": "numCitedBy"},
        {"key": "numCiting"},
    ]
    ```

    `format_authors` is a built-in function to format authors.

    `extra_data` should be a dictionary that use the DOI as keys and list of

    :param papers: list of paper metadata with the connections between each other
    :type papers: list
    :param extra_data: additional data about the papers
    :type extra_data: dict
    :param extra_data_use_keys: use only these keys from the labels provided, defaults to all keys in the provided extra_data
    :type extra_data_use_keys: list
    :param additional_keys: list of additional keys to use for the data
    :type additional_keys: list
    :param builtin_keys: list of keys and corresponding transformation to use for the data, defaults to [{"key": "authors", "transform": format_authors}, {"key": "year"}, {"key": "numCitedBy"}, {"key": "numCiting"}]
    :type builtin_keys: list
    :param connection_field_name: name of the field to use for the connections between papers
    :type connection_field_name: str
    """

    def __init__(
        self,
        papers,
        extra_data=None,
        extra_data_use_keys=None,
        additional_keys=None,
        builtin_keys=None,
        connection_field_name=None,
    ):

        if connection_field_name is None:
            connection_field_name = "local__referenced_to"
        self.connection_field_name = connection_field_name

        if builtin_keys is None:
            builtin_keys = [
                {"key": "authors", "transform": format_authors},
                {"key": "year"},
                {"key": "numCitedBy"},
                {"key": "numCiting"},
            ]

        self.builtin_keys = builtin_keys

        if additional_keys is None:
            if not extra_data:
                additional_keys = []
            else:
                for doi in extra_data:
                    additional_keys = [{"key": k} for k in extra_data[doi].keys()]
                    break

        self.additional_keys = additional_keys

        self.keys = builtin_keys + additional_keys

        self._papers = papers
        self.extra_data = extra_data
        self.extra_data_use_keys = extra_data_use_keys

    @property
    def papers(self):
        """Calculate papers property"""

        if self.extra_data:
            papers = add_additional_data_to_papers(
                self._papers, self.extra_data, self.extra_data_use_keys
            )
        else:
            papers = self._papers

        # Add connections
        papers = append_connections(
            papers, connection_field_name=self.connection_field_name
        )

        return papers

    @property
    def lut(self):
        """Transform the paper records into key value dictionary with the key being DOI."""
        return {p["doi"].lower(): p for p in self.papers}

    @property
    def data(self):
        scatter_data = {}
        for key in self.keys:
            scatter_data[key["key"]] = self._transform_records(
                key["key"],
                self.papers,
                default_value=key.get("default_value", None),
                transform=key.get("transform", None),
            )

        return scatter_data

    def connections(
        self, col_x_axis, col_y_axis, col_x_default=None, col_y_default=None
    ):
        """Calculate connections (node to node)

        As this is already calculating the coordinates, we have to specify the columns that are used for the x and y axis. These coordinates should be numerical.

        :param col_x_axis: name of the column to use for the x axis
        :type col_x_axis: str
        :param col_y_axis: name of the column to use for the y axis
        :type col_y_axis: str
        :param col_x_default: default value to use for the x axis, defaults to None
        :type col_x_default: str, optional
        :param col_y_default: default value to use for the y axis, defaults to None
        :type col_y_default: str, optional
        :return: list of connections
        :rtype: list
        """

        lut = self.lut
        papers = self.papers

        connection_data = [
            [
                (
                    lut[p["doi"]].get(col_x_axis, col_x_default),
                    lut[p["doi"]].get(col_y_axis, col_y_default),
                ),
                (
                    lut[pt_doi].get(col_x_axis, col_x_default),
                    lut[pt_doi].get(col_y_axis, col_y_default),
                ),
            ]
            for p in papers
            for pt_doi in p[self.connection_field_name]
        ]
        return connection_data

    @staticmethod
    def _transform_records(key, papers, default_value=None, transform=None):
        """A generic parser to get and transform values from the paper records"""

        if transform is None:
            transform = lambda x: x.get(key, default_value)

        data = [transform(p) for p in papers]

        return data


if __name__ == "__main__":
    pass
