from ai.graphs.linters_graph import linters_graph

result = linters_graph.invoke({
    "repo_url": "https://github.com/ScarletFlame611/OOP_Laba"
}, {"recursion_limit": 500})

print(result)
