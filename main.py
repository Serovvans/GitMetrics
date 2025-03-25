from GitMetrics.ai.graphs.error_analysis_graph import code_analysis_graph
from IPython.display import Image, display

# result = code_analysis_graph.invoke({
#     "repo_url": "https://github.com/Serovvans/auto_pandas"
# })

# print(result)

display(Image(code_analysis_graph.get_graph().draw_mermaid_png()))