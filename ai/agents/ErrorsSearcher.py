from langgraph.prebuilt import create_react_agent
from langchain_groq import ChatGroq
from typing import TypedDict, Annotated, Optional, Dict


llm = ChatGroq(
    model="deepseek-r1-distill-qwen-32b",
    temperature=0.2,
    max_tokens=4096
)

class IssueDetail(TypedDict):
    error: str
    criticality: str
    solution: str

class CodeAnalysisOutput(TypedDict):
    """Формат структурированного ответа агента"""
    issues: Annotated[
        Optional[Dict[str, IssueDetail]], 
        "Словарь с найденными проблемами в коде"
    ]
    overall_assessment: Annotated[
        Optional[str], 
        "Общая оценка качества кода"
    ]
    recommendations: Annotated[
        Optional[str], 
        "Общие рекомендации по улучшению кода"
    ]

ErrorSearcher = create_react_agent(
    model=llm,
    tools=[],
    response_format=CodeAnalysisOutput
)