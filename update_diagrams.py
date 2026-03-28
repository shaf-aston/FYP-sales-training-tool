import os
import re

dir_path = "Documentation/diagrams/"

# We will apply styling and markdown formatting to diagram 1 to make it prettier and clearer.
with open(os.path.join(dir_path, "01_system_context.mmd"), "r", encoding="utf-8") as f:
    d1 = f.read()

d1 = d1.replace("User([", "User([\"<b>User & Browser</b><br/>")
# Make headers bold
d1 = re.sub(r'([^"A-Za-z])(app\.py|security\.py|chatbot\.py|flow\.py|analysis\.py|content\.py|loader\.py)', r'\1<b>\2</b>', d1)

# Add styling classes
style = """
classDef primary fill:#e3f2fd,stroke:#2b81d6,stroke-width:2px;
classDef core fill:#fff3e0,stroke:#1565c0,stroke-width:2px;
classDef config fill:#f1f8e9,stroke:#558b2f,stroke-width:2px;
classDef provider fill:#fce4ec,stroke:#ef6c00,stroke-width:2px;
classDef db fill:#eceff1,stroke:#455a64,stroke-width:2px;

class App,Sec primary;
class Chatbot,FlowEng,NLU,ContentLayer,Loader core;
class YAML config;
class GP,OP,SP,DP provider;
class FS db;
"""

if "classDef primary" not in d1:
    d1 = d1.replace("%% ─── EDGES", style + "\n%% ─── EDGES")

with open(os.path.join(dir_path, "01_system_context.mmd"), "w", encoding="utf-8") as f:
    f.write(d1)

# Diagram 2
with open(os.path.join(dir_path, "02_component_dependencies.mmd"), "r", encoding="utf-8") as f:
    d2 = f.read()

# Consolidate config files
d2_simpl = d2.replace(
"""    %% ── Config reads (all @lru_cache)
    loader    --> yaml_sig
    loader    --> yaml_ana
    loader    --> yaml_prod
    loader    --> yaml_tac
    loader    --> yaml_ada
    loader    --> yaml_ov
    loader    --> yaml_pro
    loader    --> yaml_qz
    loader    --> yaml_var""",
"""    %% ── Config reads (merged to reduce mess)
    loader    --> yaml_all["9 YAML Config Files (signals, products, rules)"]""")

d2_simpl = d2_simpl.replace(
"""    app       --> chatbot
    app       --> security
    app       --> trainer
    app       --> quiz
    app       --> prospect
    app       --> knowledge
    app       --> analytics""",
"""    app --> chatbot & security
    app --> trainer & quiz & prospect & knowledge & analytics""")

d2_simpl = d2_simpl.replace(
"""    factory   --> groq_p
    factory   --> or_p
    factory   --> sam_p
    factory   --> dummy_p""",
"""    factory --> groq_p & or_p & sam_p & dummy_p""")

# Clean subgraph nodes that are no longer referenced
d2_simpl = re.sub(r'yaml_[a-z]+\[".*?"\]\n', '', d2_simpl)

if "classDef" not in d2_simpl:
    d2_simpl = d2_simpl.replace("graph TD", "graph TD\n" + style)

with open(os.path.join(dir_path, "02_component_dependencies.mmd"), "w", encoding="utf-8") as f:
    f.write(d2_simpl)

