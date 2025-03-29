from langgraph.prebuilt import create_react_agent
from langchain_groq import ChatGroq
from ai.utils import load_agent_config, load_model_config
from ai.tools.git_tools import get_code_author

agents_config = load_agent_config()
models_config = load_model_config()


llm = ChatGroq(
    model=models_config['TaskAllocationAgent']['model'],
    temperature=models_config['TaskAllocationAgent']['temperature'],
    max_tokens=5000
)

TaskAllocationAgent = create_react_agent(
    model=llm,
    tools=[get_code_author],
    prompt=agents_config['TaskAllocationAgent']['system_prompt'],
    name="TaskAllocationAgent"
)


__all__ = ["TaskAllocationAgent"]