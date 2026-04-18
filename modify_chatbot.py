import re

with open("src/chatbot/chatbot.py", "r") as f:
    content = f.read()

start_idx = content.find("def _get_objection_pathway_safe(")
end_idx = content.find("@dataclass\nclass ChatResponse:")

if start_idx != -1 and end_idx != -1:
    new_content = content[:start_idx] + content[end_idx:]
    with open("src/chatbot/chatbot.py", "w") as f:
        f.write(new_content)
    print("Success chatbot")
else:
    print("Indices not found")
