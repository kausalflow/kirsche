from pathlib import Path
from typing import Union

import pyecharts.options as opts
from pyecharts.charts import Graph

from kirsche.utils.graph import PaperGraph
from kirsche.utils.io import load_json


def load_graph(connections_json: Union[str, Path], title: str) -> PaperGraph:
    """Load json file that contains the paper connection information, and build a graph using it.

    :param connections_json: json file that contains the paper connection information
    :param title: title of the graph which will be shown in the top of the chart
    """

    data = load_json(connections_json)

    if data:
        g = PaperGraph(data, title=title)
    else:
        raise ValueError(f"No data in json file: {connections_json}!")

    return g


def visualize(nodes: list, edges: list, title: str, target: Union[str, Path]) -> None:
    """Generate interactive graphs

    :param nodes: nodes of the graph
    :param edges: edges of the graph
    :param title: title of the graph which will be shown in the top of the chart
    :param target: target file path
    """

    # Build the graph and export it to html file
    (
        Graph(init_opts=opts.InitOpts(width="1600px", height="800px"))
        .add(
            series_name="",
            nodes=nodes,
            links=edges,
            layout="none",
            is_roam=True,
            is_focusnode=True,
            label_opts=opts.LabelOpts(is_show=False),
            linestyle_opts=opts.LineStyleOpts(width=10, curve=0.3, opacity=0.5),
        )
        .set_global_opts(title_opts=opts.TitleOpts(title=title))
        .render(target)
    )


def make_chart(
    connections_json: Union[Path, str], target: Union[Path, str], title: str
) -> None:
    """Generate interactive graphs

    :param connections_json: json file that contains the paper connection information
    :param target: target file path
    :param title: title of the graph which will be shown in the top of the chart
    """

    g = load_graph(connections_json, title)

    nodes = g.nodes
    edges = g.edges

    visualize(nodes, edges, g.title, target)


if __name__ == "__main__":
    import json

    paper_connections = "tests/data/io/test.json"
    target = "tests/data/visualize/test.html"

    make_chart(paper_connections, target, "This is an Experiment")
