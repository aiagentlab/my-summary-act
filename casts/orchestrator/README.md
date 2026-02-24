
# Orchestrator Module

## Overview
This module defines the Orchestrator LangGraph graph responsible for running and extracting insights.

## Structure
```
orchestrator/
├── modules/
│   ├── agents.py      # Agents (optional)
│   ├── conditions.py  # Conditional logic (optional)
│   ├── models.py      # Models (optional)
│   ├── nodes.py       # Graph nodes (required)
│   ├── prompts.py     # Prompts (optional)
│   ├── middlewares.py # Middleware configurations (optional)
│   ├── state.py       # State definition (required)
│   ├── tools.py       # Tools (optional)
│   └── utils.py       # Utilities (optional)
├── pyproject.toml     # Package metadata
├── README.md          # This document
└── graph.py           # Graph definition
```

## Usage
```python
from casts.orchestrator.graph import orchestrator_graph

initial_state = {
    "query": "Hello, Act"
}

result = orchestrator_graph().invoke(initial_state)
```

## Extending
1. Add new state in `modules/state.py`
2. Add new node classes in `modules/nodes.py`
3. Define agents/conditions/middlewares/tools/prompts/models/utils if needed
4. Wire nodes into the graph in `graph.py`


