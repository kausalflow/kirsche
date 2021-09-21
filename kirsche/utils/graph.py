import math


class PaperGraph:
    """A graph object to hold graphs

    :param paper_connections: a list of dictionaries that specifies the connections between papers
    :param title: the title of the graph
    """

    def __init__(self, paper_connections: list, title: str = None):

        if not isinstance(paper_connections, list):
            raise TypeError("The connections paper_connections must be a dictionary")

        self.nodes, self.edges = self._extract_nodes_and_edges(paper_connections)
        self.title = title

    def _calculate_node(self, node: dict, schema: dict):
        """calculate the node"""
        simplified_node = {}
        for k, v in schema.items():
            v_key = v["key"]
            k_values = node.get(v_key, v.get("default"))
            if v.get("transform"):
                k_values = v["transform"](k_values)
            simplified_node[k] = k_values

        return simplified_node

    def _extract_nodes_and_edges(
        self, connections: list, node_schema: dict = None, edge_schema: dict = None
    ):
        """extract nodes and edges from connections

        :param connections: a list of dictionaries that specifies the connections between papers
        :param node_schema: a dictionary that specifies how the nodes are extracted
        :param edge_schema: a dictionary that specifies how the edges are built
        """

        if node_schema is None:
            node_schema = {
                "name": {
                    "key": "title",
                    "default": "No Title",
                },
                "id": {"key": "doi"},
                "symbolSize": {
                    "key": "numCitedBy",
                    "transform": lambda x: 5 * math.log(x + 2),
                },
                "x": {"key": "year"},
                "y": {"key": "numCiting"},
            }

        if edge_schema is None:
            edge_schema = {"source": "doi", "target": "doi"}

        edges = []
        nodes = []
        for c in connections:
            c_id = c[node_schema["id"]["key"]]
            if c_id not in [n["id"] for n in nodes]:
                c_simplified = self._calculate_node(c, node_schema)
                nodes.append(c_simplified)
            c_to = c.get("local__referenced_to", [])
            for c_to_node in c_to:
                c_to_node_edge = {
                    "source": c_id,
                    "target": c_to_node,
                }
                edges.append(c_to_node_edge)

        return nodes, edges

    def __str__(self):
        return f"Graph: {self.title}\n  nodes: {self.nodes}\n  edges: {self.edges}"


if __name__ == "__main__":
    import json

    with open("tests/data/io/test__connection_enhanced.json", "r") as f:
        paper_connections = json.load(f)

    g = PaperGraph(paper_connections)
    print(g)
