import re

with open("src/chatbot/content.py", "r") as f:
    content = f.read()

start_idx = content.find("OFLOWS = load_objection_flows()")
end_idx = content.find("def _build_tactic_guidance(")

if start_idx != -1 and end_idx != -1:
    new_content = content[:start_idx] + "from .objection import _build_objection_context\n\n" + content[end_idx:]
    with open("src/chatbot/content.py", "w") as f:
        f.write(new_content)
    print("Success content")
else:
    print("Indices not found")
