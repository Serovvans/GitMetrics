from ai.graphs.linters_graph import linters_graph
from IPython.display import Image, display

# result = code_analysis_graph.invoke({
#     "repo_url": "https://github.com/Serovvans/auto_pandas"
# })

# print(result)

png_data = linters_graph.get_graph().draw_mermaid_png()
with open('workflow_graph.png', 'wb') as f:
    f.write(png_data)

print("Граф сохранен как workflow_graph.png")