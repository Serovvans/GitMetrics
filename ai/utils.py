import yaml

def load_agent_config():
    with open("ai/config/agents.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)