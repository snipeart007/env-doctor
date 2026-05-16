# env-doctor — Current Implementation State

## Feature Status Summary

| Feature | Status | Notes |
| :--- | :--- | :--- |
| **Database Update** (`update-db`) | ✅ Working | Compiles YAML files to local SQLite successfully. |
| **Env Inspection** (`inspect`) | ✅ Working | Detects OS, Python, and CUDA status. |
| **Compatibility Check** (`check`) | ✅ Working | Correctly identifies known broken combinations. |
| **Stack Recommend** (`recommend`) | ✅ Working | Ranks and suggests stable package sets. |
| **Local Reporting** (`report-incompatibility`) | ✅ Working | Captures traces and saves JSON reports locally. |
| **VRAM Estimation** (`vram`) | ⚠️ Unstable | Fails to parse many HF model architectures (e.g., gpt2). |
| **Dependency Patch** (`patch`) | ❌ Broken | Crashes due to a database session error (`DetachedInstanceError`). |
| **AI Reporting** (`--submit`) | ❌ Mocked | Watsonx and GitHub PR features are stubs/TODOs. |

## Implementation Details

### Usable Components
- **Core CLI Engine**: Typer-based interface with Rich UI components.
- **Database Schema**: SQLite implementation with 8 core tables (Packages, Versions, Dependencies, Rules, Stacks, etc.).
- **Compatibility Engine**: Version range matching and severity scoring logic.
- **Recommendation Engine**: Scoring algorithm based on confidence, overlap, and recency.

### Current Blockers & Technical Debt
1.  **SQLAlchemy Session Management**: The `patch` command fails because database objects are accessed after the session has closed.
2.  **VRAM Model Mapping**: The `vram` engine lacks robust mapping for diverse HuggingFace model configurations.
3.  **Backend Integration**: `ai_analyzer.py` and `pr_creator.py` are currently shells with TODOs for watsonx and GitHub API integration.

## Out of Scope (Initial Phase)
- Windows support (partially working but not officially supported).
- Apple Metal, ROCm, TPU support.
- TensorFlow ecosystem.
- Distributed training & Kubernetes.
