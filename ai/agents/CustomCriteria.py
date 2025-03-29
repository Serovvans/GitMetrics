from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.3,
    max_tokens=7000
)

CustomCriteria = create_react_agent(
    model=llm,
    tools=[]
)