"""
Repository Analysis Agents Module
"""
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from ai.tools.rag_tool import retrieve_context

llm = ChatGroq(
        model="llama3-70b-8192",
        temperature=0.4,
        max_tokens=7000
    )

tools = [retrieve_context]
ChatAgent = create_react_agent(
        model=llm,
        tools=tools
    )
