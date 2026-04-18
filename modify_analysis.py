import re

with open("src/chatbot/analysis.py", "r") as f:
    content = f.read()

# Find the start of classify_objection
start_idx = content.find("def classify_objection(")
# Find the end: right before "def should_trigger_web_search("
end_idx = content.find("def should_trigger_web_search(")

if start_idx != -1 and end_idx != -1:
    new_content = content[:start_idx] + "from .objection import classify_objection, ObjectionPathway, analyze_objection_pathway, get_reframe_sequence\n\n\n# get_objection_data removed (unused); use `classify_objection()` directly where needed\n\n\n" + content[end_idx:]
    with open("src/chatbot/analysis.py", "w") as f:
        f.write(new_content)
    print("Success")
else:
    print("Indices not found")
