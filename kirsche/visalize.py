import pyecharts.options as opts
from pyecharts.charts import Graph



def visualize(nodes, edges, target, title):
    """Generate interactive graphs"""

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
