from langgraph.prebuilt import create_react_agent
from langchain_groq import ChatGroq


llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
    max_tokens=5000
)

ErrorSearcher = create_react_agent(
    model=llm,
    tools=[]
)