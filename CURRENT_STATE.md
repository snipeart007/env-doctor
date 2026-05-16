# env-doctor — Current Implementation State

## Feature Status Summary

| Feature | Status | Notes |
| :--- | :--- | :--- |
| **Database Update** (`update-db`) | ✅ Working | Compiles YAML files to local SQLite successfully. |
| **Env Inspection** (`inspect`) | ✅ Working | Detects OS, Python, and CUDA status. |
| **Compatibility Check** (`check`) | ✅ Working | Correctly identifies known broken combinations. |
| **Stack Recommend** (`recommend`) | ✅ Working | Ranks and suggests stable package sets. |
| **Local Reporting** (`report-incompatibility`) | ✅ Working | Captures code/outputs cell-by-cell in Markdown. |
| **VRAM Estimation** (`vram`) | ⚠️ Unstable | Fails to parse many HF model architectures (e.g., gpt2). |
| **Dependency Patch** (`patch`) | ❌ Broken | Crashes due to a database session error (`DetachedInstanceError`). |
| **AI Reporting** (`--submit`) | ⚠️ Partial | Watsonx Orchestrate & MCP server ready; endpoint URL pending. |

## Implementation Details

### Usable Components
- **Core CLI Engine**: Typer-based interface with Rich UI components.
- **Database Schema**: SQLite implementation with 8 core tables (Packages, Versions, Dependencies, Rules, Stacks, etc.).
- **Compatibility Engine**: Version range matching and severity scoring logic.
- **Reporting System**: Markdown-based report generator with cell-by-cell notebook execution.
- **MCP Server**: FastMCP server with tools to update the GitHub compatibility database.

### Current Blockers & Technical Debt
1.  **SQLAlchemy Session Management**: The `patch` command fails because database objects are accessed after the session has closed.
2.  **VRAM Model Mapping**: The `vram` engine lacks robust mapping for diverse HuggingFace model configurations.
3.  **Endpoint Integration**: The `_submit_to_watsonx` function in `report.py` requires a final endpoint URL and API key wiring.


## Out of Scope (Initial Phase)
- Windows support (partially working but not officially supported).
- Apple Metal, ROCm, TPU support.
- TensorFlow ecosystem.
- Distributed training & Kubernetes.
