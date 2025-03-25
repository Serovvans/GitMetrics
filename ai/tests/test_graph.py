from GitMetrics.ai.graphs.error_analysis_graph import code_analysis_graph

result = code_analysis_graph.invoke({
    "repo_url": "https://github.com/Serovvans/auto_pandas"
})

print(result["analysis_results"])
print(result["error"])