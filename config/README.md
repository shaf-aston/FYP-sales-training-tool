# Configuration Guide

This project uses YAML files for easy configuration management. All configuration files are located in the `config/` directory.

## Configuration Files

### 1. `signals.yaml`
Defines behavioral signal keywords used by the NLU (Natural Language Understanding) system to detect user intent and state.

**Categories:**
- `impatience`: Keywords indicating user wants quick answers
- `commitment`: Words showing user is ready to proceed
- `objection`: Phrases expressing resistance or concerns
- `walking`: Signals user is leaving/disengaging
- `low_intent`: Phrases indicating browsing/no immediate need
- `guarded`: Short, defensive responses
- `high_intent`: Strong buying signals or clear goals

**Example:**
```yaml
high_intent:
  - "want"
  - "need"
  - "looking for"
  - "trying to"
  - "help with"
  - "problem"
  - "struggling"
```

### 2. `analysis_config.yaml`
Contains thresholds and parameters for conversation analysis.

**Thresholds:**
- `min_substantive_word_count`: Minimum words for a "substantive" answer (default: 8)
- `short_message_limit`: Maximum words considered "short" (default: 4)
- `question_fatigue_threshold`: Number of questions triggering fatigue warning (default: 2)
- `validation_loop_threshold`: Number of validations triggering repetition warning (default: 2)
- `recent_history_window`: Number of turns to check for goal priming (default: 10)
- `recent_text_messages`: Number of recent messages to analyze for intent (default: 3)

**Goal Indicators:**
Keywords that lock user intent to HIGH (goal priming).

**Preference Keywords:**
Terms used to extract user preferences from conversation.

**Example:**
```yaml
thresholds:
  min_substantive_word_count: 8
  short_message_limit: 4
  question_fatigue_threshold: 2
```

### 3. `product_config.yaml`
Maps product types to sales strategies and context descriptions.

**Strategies:**
- `consultative`: Deep IMPACT framework (Intent → Logical → Emotional → Pitch → Objection)
- `transactional`: Fast pitch approach (Intent → Pitch → Objection)

**Example:**
```yaml
products:
  luxury_cars:
    strategy: "consultative"
    context: "luxury vehicles"
  
  watches:
    strategy: "transactional"
    context: "watches"

default:
  strategy: "consultative"
  context: "products/services"
```

## Modifying Configuration

### To Add New Signal Keywords:
1. Open `config/signals.yaml`
2. Add your keyword to the appropriate category
3. Restart the application (changes are cached)

### To Adjust Analysis Thresholds:
1. Open `config/analysis_config.yaml`
2. Modify the threshold values
3. Restart the application

### To Add New Product Types:
1. Open `config/product_config.yaml`
2. Add new product entry under `products:`
3. Specify strategy (`consultative` or `transactional`) and context
4. Restart the application

## Configuration Caching

Configuration files are loaded once and cached for performance using `@lru_cache`. 

**To force reload during development:**
```python
from src.chatbot.config_loader import reload_configs
reload_configs()
```

## Benefits of YAML Configuration

1. **Easy Updates**: Modify keywords and thresholds without touching Python code
2. **Version Control**: Track configuration changes separately from logic
3. **Environment-Specific**: Easy to swap config files for different environments
4. **Validation**: YAML syntax errors are caught at load time
5. **Collaboration**: Non-technical stakeholders can adjust keywords

## File Locations

```
Sales roleplay chatbot/
├── config/                      # Configuration directory
│   ├── signals.yaml            # Behavioral signal keywords
│   ├── analysis_config.yaml    # NLU analysis parameters
│   └── product_config.yaml     # Product-to-strategy mappings
├── src/
│   └── chatbot/
│       └── config_loader.py    # YAML loading utilities
└── requirements.txt            # Includes pyyaml>=6.0
```

## Troubleshooting

**"Config file not found" error:**
- Ensure `config/` directory exists in project root
- Verify YAML files are present and named correctly
- Check file permissions

**YAML parsing errors:**
- Validate YAML syntax using online validators
- Ensure proper indentation (2 spaces, no tabs)
- Check for special characters requiring quotes

**Changes not reflected:**
- Configuration is cached - restart the application
- For development, use `reload_configs()` to clear cache
