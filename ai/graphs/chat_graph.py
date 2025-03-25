import json
from typing import TypedDict, Dict, Any

from langchain_core.messages import HumanMessage, AIMessage
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from ai.utils import load_agent_config
from ai.agents.Chat import ChatAgent


class ChatState(TypedDict):
    """State for the chat workflow"""
    messages: list
    vector_db_path: str
    

def is_code_related(state: ChatState):
    """Determine if the user message is related to code or programming"""
    agent_config = load_agent_config()
    prompt_template = agent_config['ChatAgent']['is_code_related_prompt']
    
    last_message = state['messages'][-1].content
    
    prompt = prompt_template.format(last_message=last_message)
    
    llm = ChatGroq(
        model="deepseek-r1-distill-llama-70b",
        temperature=0,
        max_tokens=10
    )
    
    response = llm.invoke(prompt)
    

    return {"is_code_related": "no" not in response.content, 
            "reasoning": ""}


def process_code_related_query(state: ChatState):
    """Process queries that are related to code"""
    agent_config = load_agent_config()
    system_prompt = agent_config['ChatAgent']['system_prompt'].format(
        vector_db_path=state["vector_db_path"]
    )
    context_message = agent_config['ChatAgent']['context_message']
    
    # Get the last user message
    last_message = ""
    for message in reversed(state["messages"]):
        if isinstance(message, HumanMessage):
            last_message = message.content
            break
    
    user_prompt = context_message.format(last_message=last_message)
    
    # Prepare the messages for the agent
    agent_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    # Invoke the agent
    result = ChatAgent.invoke({"messages": agent_messages})
    
    # Extract the response and add it to messages
    ai_message = AIMessage(content=result["messages"][-1].content)
    
    return {"messages": state["messages"] + [ai_message]}


def handle_non_code_query(state: ChatState):
    """Handle queries that are not related to code"""
    # Create a polite refusal message
    refusal_message = AIMessage(
        content="Я могу помочь только с вопросами, связанными с кодом, программированием, "
                "разработкой ПО или качеством кода. Пожалуйста, задайте вопрос, относящийся "
                "к этим темам."
    )
    
    return {"messages": state["messages"] + [refusal_message]}


def route_query(state: Dict[str, Any]):
    """Route the query based on whether it's code-related or not"""
    if state.get("is_code_related", False):
        return "process_code_related"
    else:
        return "handle_non_code"


def build_chat_graph():
    """Build and return the chat workflow graph"""
    # Create a new graph
    workflow = StateGraph(ChatState)
    
    # Add nodes to the graph
    workflow.add_node("check_code_related", is_code_related)
    workflow.add_node("process_code_related", process_code_related_query)
    workflow.add_node("handle_non_code", handle_non_code_query)
    
    # Set the entry point
    workflow.set_entry_point("check_code_related")
    
    # Add conditional edges based on whether the query is code-related
    workflow.add_conditional_edges(
        "check_code_related",
        route_query,
        {
            "process_code_related": "process_code_related",
            "handle_non_code": "handle_non_code"
        }
    )
    
    # Both process nodes should end the workflow
    workflow.add_edge("process_code_related", END)
    workflow.add_edge("handle_non_code", END)
    
    # Initialize memory saver for persistence
    memory = MemorySaver()
    
    # Compile the graph with memory
    return workflow.compile(checkpointer=memory)

chat_graph = build_chat_graph()
