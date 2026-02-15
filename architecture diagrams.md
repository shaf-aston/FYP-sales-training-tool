# Sales Chatbot Architecture Diagrams

## Diagram 1: Overall System Architecture (High-Level)

```mermaid
flowchart TB
    subgraph USER["👤 USER"]
        Browser["Web Browser"]
    end

    subgraph FRONTEND["🖥️ FRONTEND (index.html)"]
        UI["Chat Interface"]
        Speech["🎤 Speech Recognition"]
        TTS["🔊 Text-to-Speech"]
    end

    subgraph BACKEND["⚙️ FLASK SERVER (app.py)"]
        API["REST API Endpoints"]
        Sessions["Session Manager"]
    end

    subgraph CORE["🧠 CHATBOT BRAIN"]
        Chatbot["SalesChatbot"]
        FSM["Flow Engine (FSM)"]
        Analysis["NLU Analysis"]
        Prompts["Prompt Generator"]
    end

    subgraph LLM["🤖 LLM PROVIDERS"]
        Factory["Provider Factory"]
        Groq["☁️ Groq Cloud"]
        Ollama["🏠 Ollama Local"]
    end

    subgraph CONFIG["📁 CONFIGURATION"]
        YAML1["signals.yaml"]
        YAML2["analysis_config.yaml"]
        YAML3["product_config.yaml"]
    end

    Browser --> UI
    UI --> API
    Speech --> UI
    TTS --> UI
    
    API --> Sessions
    Sessions --> Chatbot
    
    Chatbot --> FSM
    Chatbot --> Factory
    FSM --> Analysis
    FSM --> Prompts
    Analysis --> CONFIG
    Prompts --> CONFIG
    
    Factory --> Groq
    Factory --> Ollama
    
    Groq -.->|"API Response"| Chatbot
    Ollama -.->|"Local Response"| Chatbot

    style USER fill:#e1f5fe
    style FRONTEND fill:#fff3e0
    style BACKEND fill:#f3e5f5
    style CORE fill:#e8f5e9
    style LLM fill:#fce4ec
    style CONFIG fill:#fff8e1
```

---

## Diagram 2: Chat Message Flow (Step-by-Step)

```mermaid
sequenceDiagram
    participant U as 👤 User
    participant F as 🖥️ Frontend
    participant A as ⚙️ Flask API
    participant C as 🧠 Chatbot
    participant E as 📊 FSM Engine
    participant P as 🤖 LLM Provider

    U->>F: Types message
    F->>A: POST /api/chat
    A->>A: Get session
    A->>C: chat(message)
    
    C->>E: get_current_prompt()
    E->>E: Analyze user state
    E-->>C: Stage-specific prompt
    
    C->>P: Send to LLM
    P-->>C: AI Response
    
    C->>E: add_turn(user, bot)
    C->>E: should_advance()
    
    alt Stage should advance
        E->>E: advance()
        E-->>C: New stage
    end
    
    C-->>A: Response + stage
    A-->>F: JSON response
    F-->>U: Display message
```

---

## Diagram 3: Finite State Machine (Sales Flow)

```mermaid
stateDiagram-v2
    [*] --> Intent: Start Conversation
    
    Intent --> Logical: User shows clear intent
    Intent --> Intent: Low intent (max 6 turns)
    
    Logical --> Emotional: User shows doubt
    Logical --> Pitch: User demands directness ⚡
    Logical --> Logical: Building doubt (max 5 turns)
    
    Emotional --> Pitch: User expresses stakes
    Emotional --> Emotional: Exploring feelings (max 6 turns)
    
    Pitch --> Objection: User objects or commits
    Pitch --> Pitch: Presenting solution
    
    Objection --> [*]: Deal closed ✅
    Objection --> [*]: User walks away ❌
    Objection --> Objection: Handling objections

    note right of Intent
        🎯 Goal: Understand why user is here
        📝 Technique: Elicitation statements
    end note

    note right of Logical
        🎯 Goal: Create doubt in status quo
        📝 Technique: Probing questions
    end note

    note right of Emotional
        🎯 Goal: Reveal personal stakes
        📝 Technique: Emotional mirroring
    end note

    note right of Pitch
        🎯 Goal: Present solution
        📝 Technique: Value proposition
    end note

    note right of Objection
        🎯 Goal: Handle concerns, close deal
        📝 Technique: Reframing
    end note
```

---

## Diagram 4: Provider Architecture (Switching)

```mermaid
flowchart LR
    subgraph INTERFACE["📋 Interface Contract"]
        Base["BaseLLMProvider (ABC)"]
        Base --> |"implements"| M1["chat()"]
        Base --> |"implements"| M2["is_available()"]
        Base --> |"implements"| M3["get_model_name()"]
    end

    subgraph FACTORY["🏭 Factory Pattern"]
        Create["create_provider(type)"]
        Registry["PROVIDERS Registry"]
    end

    subgraph PROVIDERS["🤖 Concrete Providers"]
        Groq["GroqProvider"]
        Ollama["OllamaProvider"]
        Future["FutureProvider..."]
    end

    subgraph USAGE["📱 Usage"]
        Chatbot["SalesChatbot"]
        Switch["switch_provider()"]
    end

    Base --> Groq
    Base --> Ollama
    Base -.-> Future

    Create --> Registry
    Registry --> Groq
    Registry --> Ollama

    Chatbot --> Create
    Chatbot --> Switch
    Switch --> Create

    style INTERFACE fill:#e3f2fd
    style FACTORY fill:#fff3e0
    style PROVIDERS fill:#e8f5e9
    style USAGE fill:#fce4ec
```

---

## Diagram 5: Edit/Rewind Flow (Bug Analysis)

```mermaid
flowchart TD
    subgraph TRIGGER["🖱️ User Action"]
        Click["Click Edit Button"]
        Click --> Modal["Enter New Text"]
    end

    subgraph API["📡 API Call"]
        Modal --> Post["POST /api/edit"]
        Post --> |"index, message"| Validate
    end

    subgraph REWIND["⏪ Rewind Process"]
        Validate --> CalcTurn["turn_index = msg_index ÷ 2"]
        CalcTurn --> Slice["old_history = history[:turn_index*2]"]
        Slice --> Reset["HARD RESET Engine"]
        Reset --> |"Clear history"| R1["conversation_history = []"]
        Reset --> |"Reset counter"| R2["stage_turn_count = 0"]
        Reset --> |"Reset stage"| R3["current_stage = 'intent'"]
    end

    subgraph REPLAY["🔄 Replay Loop"]
        R1 & R2 & R3 --> Loop["For each old turn"]
        Loop --> AddTurn["add_turn(user, bot)"]
        AddTurn --> CheckAdv["should_advance()"]
        CheckAdv --> |"Yes"| Advance["advance()"]
        CheckAdv --> |"No"| NextTurn["Next iteration"]
        Advance --> NextTurn
        NextTurn --> Loop
    end

    subgraph NEWMSG["💬 New Message"]
        Loop --> |"Done"| Chat["chat(new_message)"]
        Chat --> NewResponse["Generate new bot response"]
        NewResponse --> Return["Return updated history"]
    end

    subgraph BUG["🐛 BUG LOCATION"]
        Return --> |"Frontend receives"| Render["Re-render messages"]
        Render --> |"❌ Bug: Stale indices"| StaleIdx["Edit buttons have old msgIdx"]
    end

    style TRIGGER fill:#e1f5fe
    style API fill:#fff3e0
    style REWIND fill:#ffebee
    style REPLAY fill:#e8f5e9
    style NEWMSG fill:#f3e5f5
    style BUG fill:#ffcdd2
```

---

## Diagram 6: Chatbot Logic (Zoomed In)

```mermaid
flowchart TB
    subgraph INPUT["📥 INPUT PROCESSING"]
        UserMsg["User Message"]
        UserMsg --> BuildMsgs["Build LLM Messages Array"]
        BuildMsgs --> |"1. System prompt"| Sys["get_current_prompt()"]
        BuildMsgs --> |"2. Recent history"| Hist["Last 10 messages"]
        BuildMsgs --> |"3. Current msg"| Curr["User message"]
    end

    subgraph PROMPT["📝 PROMPT GENERATION"]
        Sys --> AnalyzeState["analyze_state()"]
        AnalyzeState --> |"intent"| IntentLevel["high/medium/low"]
        AnalyzeState --> |"guarded"| Guarded["true/false"]
        AnalyzeState --> |"question_fatigue"| Fatigue["true/false"]
        
        IntentLevel --> SelectPrompt["Select Stage Prompt"]
        Guarded --> SelectPrompt
        Fatigue --> SelectPrompt
        
        SelectPrompt --> |"Low intent"| ElicitPrompt["Elicitation Prompt"]
        SelectPrompt --> |"High intent"| StandardPrompt["Standard Stage Prompt"]
        SelectPrompt --> |"Direct request"| InfoPrompt["Information-First Prompt"]
    end

    subgraph LLM["🤖 LLM CALL"]
        ElicitPrompt & StandardPrompt & InfoPrompt --> Provider["provider.chat()"]
        Provider --> |"Success"| Response["LLM Response"]
        Provider --> |"Error"| Fallback["Fallback Message"]
    end

    subgraph STATE["📊 STATE UPDATE"]
        Response --> AddTurn["add_turn(user, bot)"]
        AddTurn --> CheckAdvance["should_advance()"]
        
        CheckAdvance --> |"Check frustration"| Frust["user_demands_directness()"]
        CheckAdvance --> |"Check urgency"| Urgency["impatience signals"]
        CheckAdvance --> |"Check rules"| Rules["ADVANCEMENT_RULES"]
        
        Frust --> |"Yes: Jump to pitch"| DirectJump["advance('pitch')"]
        Urgency --> |"Yes: Skip stage"| SkipStage["advance(target)"]
        Rules --> |"Yes: Next stage"| NextStage["advance()"]
        Rules --> |"No"| Stay["Stay in stage"]
    end

    subgraph OUTPUT["📤 OUTPUT"]
        DirectJump & SkipStage & NextStage & Stay --> Return["Return Response"]
        Fallback --> Return
        Return --> |"message, stage, strategy"| Client["Send to Frontend"]
    end

    style INPUT fill:#e3f2fd
    style PROMPT fill:#fff3e0
    style LLM fill:#e8f5e9
    style STATE fill:#f3e5f5
    style OUTPUT fill:#e1f5fe
```

---

## Diagram 7: Configuration & Analysis Flow

```mermaid
flowchart LR
    subgraph YAML["📁 YAML Config Files"]
        S["signals.yaml"]
        A["analysis_config.yaml"]
        P["product_config.yaml"]
    end

    subgraph LOADER["📦 Config Loader"]
        Load["load_yaml()"]
        Cache["@lru_cache"]
        S --> Load
        A --> Load
        P --> Load
        Load --> Cache
    end

    subgraph SIGNALS["🚦 Signal Detection"]
        Cache --> |"signals"| Keywords["Keyword Lists"]
        Keywords --> |"impatience"| Imp["'just show me', 'hurry'..."]
        Keywords --> |"commitment"| Comm["'yes', 'let's do it'..."]
        Keywords --> |"objection"| Obj["'but', 'expensive'..."]
        Keywords --> |"low_intent"| Low["'just browsing'..."]
        Keywords --> |"high_intent"| High["'need', 'want'..."]
    end

    subgraph ANALYSIS["🔬 Analysis Functions"]
        Imp & Comm & Obj & Low & High --> Match["text_contains_any_keyword()"]
        Match --> State["analyze_state()"]
        State --> Intent["Intent Level"]
        State --> Guard["Guarded Detection"]
        State --> QFatigue["Question Fatigue"]
    end

    subgraph OUTPUT["📤 Output"]
        Intent --> Prompt["Prompt Selection"]
        Guard --> Prompt
        QFatigue --> Prompt
        Prompt --> Stage["Stage-Specific Behavior"]
    end

    style YAML fill:#fff8e1
    style LOADER fill:#e8f5e9
    style SIGNALS fill:#e3f2fd
    style ANALYSIS fill:#f3e5f5
    style OUTPUT fill:#fce4ec
```

---

## Legend

| Symbol | Meaning |
|--------|---------|
| 👤 | User |
| 🖥️ | Frontend |
| ⚙️ | Backend/API |
| 🧠 | Core Logic |
| 🤖 | LLM/AI |
| 📁 | Configuration |
| ✅ | Success |
| ❌ | Failure |
| ⚡ | Override/Skip |
| 🐛 | Bug Location |

---

## Simple Explanation (For a 6-Year-Old)

### What Does This Chatbot Do?

```
┌─────────────────────────────────────────────────┐
│  🎭 IMAGINE A HELPFUL ROBOT SALESPERSON 🤖     │
├─────────────────────────────────────────────────┤
│                                                 │
│  1. 👋 HELLO! (Intent Stage)                   │
│     Robot asks: "What do you need?"            │
│     Like when a shop assistant says "Hi!"      │
│                                                 │
│  2. 🤔 THINKING (Logical Stage)                │
│     Robot asks: "Is your current thing broken?"│
│     Like asking "Why do you want new shoes?"   │
│                                                 │
│  3. 💖 FEELINGS (Emotional Stage)              │
│     Robot asks: "How does that make you feel?" │
│     Like asking "Are you sad your toy broke?"  │
│                                                 │
│  4. 🎁 HERE'S THE ANSWER! (Pitch Stage)        │
│     Robot says: "I have just the thing!"       │
│     Like showing you the perfect toy           │
│                                                 │
│  5. 🙋 ANY QUESTIONS? (Objection Stage)        │
│     Robot says: "Is the price okay?"           │
│     Like asking "Do you have enough pocket     │
│     money?"                                     │
│                                                 │
└─────────────────────────────────────────────────┘

The robot listens to what you say and decides 
which step to be on. If you're in a hurry, 
it skips to showing you options faster! ⚡
```

### How Does the Robot Talk?

```
┌─────────────────────────────────────────────────┐
│  📱 YOUR PHONE          →   🏪 SHOP SERVER     │
│  (Where you type)            (Flask app)        │
│                                                 │
│       ↓                           ↓             │
│                                                 │
│  💬 "I need a car"     →   🧠 ROBOT BRAIN     │
│                              (Chatbot)          │
│                                                 │
│       ↓                           ↓             │
│                                                 │
│  🤖 AI HELPER          ←   📝 INSTRUCTIONS    │
│  (Groq or Ollama)           (Prompts)          │
│                                                 │
│       ↓                                         │
│                                                 │
│  💬 "What kind of car do you want?"            │
│                                                 │
└─────────────────────────────────────────────────┘

It's like sending a letter to a smart friend
who reads your letter and writes back! ✉️
```