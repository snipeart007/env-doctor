# env-doctor — Revised System Design & Implementation Plan

# Vision

`env-doctor` is a local-first runtime compatibility intelligence and VRAM analysis tool for the HuggingFace + Torch + CUDA ecosystem.

The system acts as:

```txt
A user-managed dependency intelligence repository
+
A powerful local compatibility analysis CLI
```

It is NOT:
- a package manager
- a dependency resolver
- a pip replacement
- a uv replacement

Instead, it solves:
- undocumented runtime incompatibilities
- CUDA/toolchain mismatches
- unstable package combinations
- torch ABI breakages
- wheel availability problems
- VRAM estimation inaccuracies
- OOM debugging
- environment instability

Core philosophy:

```txt
"Will this setup ACTUALLY work?"
```

instead of:

```txt
"Can pip install this?"
```

---

# PRIMARY PRODUCT MODEL

The product consists of:

## 1. Community Dependency Intelligence Repository

A GitHub-hosted database repository containing:
- compatibility rules
- stable stacks
- wheel availability
- runtime profiles
- package metadata
- curated ecosystem intelligence

Think of this as:

```txt
APT repository metadata
+
community-maintained runtime compatibility intelligence
```

---

## 2. Local CLI Intelligence Engine

The CLI:
- downloads latest DB snapshot
- caches locally
- performs ALL compatibility analysis locally
- performs ALL recommendations locally
- performs ALL VRAM analysis locally

No always-online backend required.

---

# IMPORTANT PRODUCT POSITIONING

This is NOT:
```txt
a dependency resolver
```

This IS:
```txt
a dependency intelligence system
```

The system focuses on:
- operational compatibility
- runtime stability
- CUDA compatibility
- ecosystem sanity
- stable stack discovery

---

# Core Product Goals

The tool should help users:

```txt
1. Discover stable package combinations
2. Avoid ecosystem breakage
3. Understand VRAM requirements
4. Detect runtime risks
5. Patch unstable environments
6. Share compatibility knowledge
```

---

# Product Scope (Phase 1)

Supported:
- Linux
- NVIDIA CUDA
- cloud notebook environments
- Linux desktop environments

Supported ecosystem:
- torch
- transformers
- accelerate
- peft
- trl
- unsloth
- flash-attn
- bitsandbytes
- datasets
- sentence-transformers
- vllm
- llama-index
- langchain
- chromadb
- faiss

Not supported initially:
- Windows
- ROCm
- Apple Metal
- TensorFlow
- TPU
- Kubernetes
- distributed training

---

# System Architecture

```txt
                    ┌───────────────────────┐
                    │ GitHub DB Repository  │
                    └──────────┬────────────┘
                               │
                               ▼
                    ┌───────────────────────┐
                    │ Local Database Cache  │
                    └──────────┬────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
┌────────────────┐    ┌────────────────┐    ┌────────────────┐
│ Compatibility  │    │ Recommendation │    │ VRAM Engine    │
│ Engine         │    │ Engine         │    │                │
└────────────────┘    └────────────────┘    └────────────────┘
                               │
                               ▼
                    ┌───────────────────────┐
                    │ CLI Interface         │
                    └───────────────────────┘
```

---

# Core Design Philosophy

## The database is the product.

The CLI is:
- an execution engine
- a recommendation engine
- a compatibility intelligence engine

But the accumulated:
- compatibility data
- stability rules
- ecosystem knowledge

becomes the real moat.

---

# Community-Driven Database Model

The database repository is:
- GitHub-based
- versioned
- transparent
- user-managed
- PR-driven

Users can:
- submit compatibility rules
- add stable stacks
- improve runtime profiles
- update wheel metadata
- add package intelligence

---

# Database Repository Structure

The upstream repository uses a partitioned YAML system for easy Git-based contributions and clear version tracking.

```txt
env-doctor-db/
├── compatibility/
│   ├── t/
│   │   └── torch/
│   │       ├── 2.1.yaml
│   │       ├── 2.2.yaml
│   │       └── 2.3.yaml
│   └── t/
│       └── transformers/
│           └── 4.38.yaml
├── stable-stacks/
├── wheel-index/
├── runtimes/
└── metadata.json
```

**Key Rules:**
- **Deterministic UIDs**: Every entry uses a deterministic hash (e.g., SHA-256 of package+version+platform) as its UID, allowing decentralized generation.
- **Full History**: The local database retains the **entire history** of all package versions and compatibility rules to ensure historical context.
- **Granularity**: Files are partitioned alphabetically (e.g., `t/torch/`) to manage directory size.
- **Data Integrity**: Compatibility data is strictly unique to specific package version combinations.

---

# metadata.json

Tracks:
- DB schema version
- release timestamp
- compatibility snapshot version

Example:

```json
{
  "db_version": "1.0.0",
  "generated_at": "2026-05-15T12:00:00Z",
  "schema_version": 1
}
```

---

# VERY IMPORTANT:
# Automatic Initial Database Population

The system should automatically bootstrap itself by parsing:
- PyPI package metadata
- dependency constraints
- wheel metadata
- Python version requirements

This is CRITICAL.

The manually curated compatibility rules should augment:
- real dependency metadata
- real version constraints

NOT replace them.

---

# Automatic Metadata Collection System

# Goal

Automatically build:
- package dependency graphs
- version compatibility maps
- wheel availability indexes

from PyPI metadata.

---

# Metadata Sources

## Primary Sources

- PyPI JSON API
- package metadata
- wheel metadata
- GitHub releases

---

# PyPI JSON API

Endpoint:

```http
GET https://pypi.org/pypi/{package}/json
```

Example:

```http
GET https://pypi.org/pypi/transformers/json
```

---

# Example Response Fields

```json
{
  "info": {
    "requires_python": ">=3.9",
    "requires_dist": [
      "torch>=2.1",
      "accelerate>=0.26"
    ]
  },

  "releases": {
    "4.52.0": [
      ...
    ]
  }
}
```

---

# Automatic Dependency Parsing

The system should parse:
- requires_dist
- requires_python
- wheel metadata
- extras_require

---

# Python Libraries

Use:
- packaging
- importlib.metadata
- semantic_version

---

# Example Dependency Parsing

```python
from packaging.requirements import Requirement

req = Requirement("torch>=2.1")

print(req.name)
print(req.specifier)
```

---

# Database Bootstrap Process

```txt
Package List
    ↓
Fetch PyPI Metadata
    ↓
Extract Dependency Constraints
    ↓
Extract Python Requirements
    ↓
Extract Wheel Metadata
    ↓
Populate Base Compatibility Graph
    ↓
Apply Curated Compatibility Rules
```

---

# VERY IMPORTANT

PyPI metadata ONLY provides:

```txt
declared compatibility
```

But NOT:
- runtime stability
- CUDA ABI compatibility
- ecosystem sanity
- operational compatibility

That is why:
- community intelligence
- curated rules
- stable stack recommendations

are still required.

---

# Dependency Intelligence Layers

The database should contain TWO layers:

---

# Layer 1 — Automatic Metadata Layer

Automatically generated from:
- PyPI
- wheel metadata
- package requirements

Provides:
- dependency graph
- version constraints
- Python requirements
- wheel availability

---

# Layer 2 — Curated Intelligence Layer

User-managed compatibility intelligence.

Provides:
- runtime instability warnings
- known broken combinations
- stable stack recommendations
- ecosystem-specific rules
- CUDA/runtime guidance

---

# Example

PyPI metadata may say:

```txt
flash-attn >= torch 2.6
```

But curated intelligence may say:

```txt
flash-attn 2.8 unstable with torch 2.7 on CUDA 12.6
```

This distinction is ESSENTIAL.

---

# Local-First Architecture

The CLI:
- downloads DB snapshots
- caches locally
- performs all analysis locally

No mandatory cloud dependency.

---

# Database Update Flow

1. **Fetch**: CLI downloads the latest YAML snapshots from the GitHub repository.
2. **Compile**: Local engine converts and indexes YAML files into a high-performance **SQLite** database.
3. **Deterministic Logic**: Consistency is ensured by the deterministic nature of the compiler; the codebase guarantees that the same input YAML files always produce an identical SQLite structure across all platforms.
4. **History Retention**: The compiler ensures all historical records are preserved during the update process.
5. **Cache**: The SQLite database is stored locally (e.g., `~/.cache/env-doctor/intelligence.db`).

---

# CLI Design

---

# Update Database

```bash
env-doctor update-db
```

Downloads YAML files and compiles the local SQLite intelligence cache.

---

# Inspect Environment

```bash
env-doctor inspect
```

---

# Check Compatibility

```bash
env-doctor check requirements.txt
```

---

# Recommend Stable Stack

```bash
env-doctor recommend
```

---

# VRAM Analysis

```bash
env-doctor vram \
  --model Qwen/Qwen3-32B \
  --runtime vllm \
  --quant awq
```

---

# Patch pyproject.toml

```bash
env-doctor patch pyproject.toml
```

---

# Report Incompatibility

```bash
env-doctor report-incompatibility <script_or_notebook>
```

Runs the provided Python script or Jupyter notebook locally, captures the output, and submits it for compatibility analysis.

---

# Local Project Structure

```txt
env-doctor/
├── pyproject.toml         # uv-managed project metadata
├── README.md
├── src/
│   └── env-doctor/         # Main package
│       ├── __init__.py
│       ├── main.py        # CLI Entry point (Typer)
│       ├── cli/           # CLI command definitions
│       ├── core/          # Logic (compatibility, recommendations)
│       ├── database/      # SQLite/DB management & YAML-to-SQLite compiler
│       ├── scanner/       # Local environment scanning
│       ├── vram/          # VRAM estimation engine
│       ├── reporting/     # Incompatibility reporting logic
│       └── utils/         # Shared helpers
├── tests/                 # Pytest suite
└── .python-version        # uv-managed python version (3.10+)
```

---

# Environment Setup

The project uses **uv** for lightning-fast dependency management and environment isolation.

## Recommended Tooling
- **uv**: Project management and fast installs.
- **Python**: **3.10+** (Required for modern type hints and pattern matching).
- **ruff**: Linting and formatting.
- **pytest**: Testing framework.
- **typer**: CLI framework with type hints.
- **rich**: Terminal UI and progress bars.

## Core Dependencies
- `pydantic`: Data validation for schema.
- `httpx`: Async HTTP client for DB updates/reporting.
- `packaging`: Requirement parsing.
- `nbconvert`/`nbformat`: For notebook execution in `report_incompatibility`.
- `sqlmodel`: For local intelligence cache.

---

# Incompatibility Reporting Workflow

1. **Local Execution**: The CLI runs the input script/notebook in the **user's current environment**.
2. **Environment Capture**: 
   - Captures exact versions of all installed packages (`pip list`).
   - Identifies related system info (Python, CUDA, OS).
   - Captures package-specific metadata for used dependencies.
3. **Data Submission**: The script/notebook, output trace, and environment snapshot are sent to the serverless endpoint.
4. **Authentication**: The serverless function authenticates the user using GitHub credentials.
   - // TODO: Implement GitHub Auth for MVP stage
5. **AI Analysis**: The function calls a custom agent on the **watsonx** platform.
6. **Verification**: The watsonx agent confirms if the error is a dependency compatibility issue.
7. **DB Update**: If verified, the agent proposes a unique YAML entry (with a stable ID) to the upstream repository.

---

# Database Schema

All tables use a **Global Unique ID (uid)** system to ensure consistency and avoid repeated entries.

---

# packages

```sql
CREATE TABLE packages (
    uid TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    platform_info TEXT
);
```

---

# package_versions

```sql
CREATE TABLE package_versions (
    uid TEXT PRIMARY KEY,

    package_uid TEXT NOT NULL,
    version TEXT NOT NULL,

    release_date TEXT,
    yanked BOOLEAN DEFAULT FALSE,
    platform_info TEXT,

    FOREIGN KEY(package_uid)
    REFERENCES packages(uid),
    
    UNIQUE(package_uid, version) -- Version uniqueness
);
```

---

# package_dependencies

AUTOMATICALLY generated from PyPI metadata.

```sql
CREATE TABLE package_dependencies (
    uid TEXT PRIMARY KEY,

    package_name TEXT,
    package_version TEXT,

    dependency_name TEXT,
    dependency_specifier TEXT,

    optional BOOLEAN,

    source TEXT,
    platform_info TEXT,
    
    UNIQUE(package_name, package_version, dependency_name)
);
```

---

# compatibility_rules

Curated intelligence layer.

```sql
CREATE TABLE compatibility_rules (
    uid TEXT PRIMARY KEY,

    package_name TEXT NOT NULL,
    package_version_range TEXT NOT NULL,

    dependency_name TEXT NOT NULL,
    dependency_version_range TEXT NOT NULL,

    compatibility_type TEXT NOT NULL, -- compatible, incompatible, etc.

    severity TEXT NOT NULL,
    confidence_level TEXT NOT NULL, -- experimental, stable, etc.

    reason TEXT,

    source_type TEXT,
    source_url TEXT,

    created_at TEXT,
    platform_info TEXT,
    
    UNIQUE(package_name, package_version_range, dependency_name, dependency_version_range)
);
```

---

# compatibility_type

```txt
compatible
incompatible
partial
runtime-risk
untested
```

---

# confidence_level

```txt
experimental
community-tested
stable
production-tested
```

---

# stable_stacks

```sql
CREATE TABLE stable_stacks (
    uid TEXT PRIMARY KEY,
    stack_name TEXT,
    cuda_version TEXT,
    confidence_level TEXT,
    notes TEXT,
    platform_info TEXT,
    
    UNIQUE(stack_name, cuda_version)
);

CREATE TABLE stable_stack_packages (
    uid TEXT PRIMARY KEY,
    stable_stack_uid TEXT NOT NULL,
    package_uid TEXT NOT NULL,
    version_string TEXT NOT NULL,
    platform_info TEXT,
    FOREIGN KEY (stable_stack_uid) REFERENCES stable_stacks(uid) ON DELETE CASCADE,
    FOREIGN KEY (package_uid) REFERENCES packages(uid),
    
    UNIQUE(stable_stack_uid, package_uid)
);
```

---

# wheel_availability

```sql
CREATE TABLE wheel_availability (
    uid TEXT PRIMARY KEY,

    package_name TEXT,
    package_version TEXT,

    python_tag TEXT,
    platform_tag TEXT,
    cuda_variant TEXT,

    available BOOLEAN,
    platform_info TEXT,
    
    UNIQUE(package_name, package_version, python_tag, platform_tag, cuda_variant)
);
```

---

# runtime_profiles

```sql
CREATE TABLE runtime_profiles (
    uid TEXT PRIMARY KEY,

    runtime_name TEXT,

    kv_overhead_multiplier REAL,
    fragmentation_multiplier REAL,

    notes TEXT,
    platform_info TEXT,
    
    UNIQUE(runtime_name)
);
```

---

# Recommendation Engine

# Goal

Recommend:
- stable environments
- production-tested combinations
- ecosystem-safe stacks

---

# Recommendation Inputs

- installed packages
- Python version
- CUDA version
- GPU architecture

---

# Recommendation Logic

```txt
Load Local DB
    ↓
Resolve Current Environment
    ↓
Detect Risky Packages
    ↓
Find Matching Stable Stacks
    ↓
Score Candidate Stacks
    ↓
Recommend Best Stable Stack
```

---

# Recommendation Priority

Prefer:
1. production-tested
2. stable
3. community-tested
4. experimental

---

# pyproject.toml Patching

# Goal

Auto-fix:
- unstable combinations
- unsupported versions
- incompatible constraints

---

# Supported Files

- pyproject.toml
- requirements.txt

---

# Parsing Libraries

Use:
- tomlkit
- tomllib

---

# VRAM Intelligence Engine

# Goal

Not:
```txt
How much VRAM theoretically?
```

Instead:
```txt
Why will this likely OOM?
```

---

# Memory Components

Estimate:
- weights
- KV cache
- activations
- optimizer states
- fragmentation
- quantization buffers

---

# HuggingFace Integration

Use:
- huggingface_hub

---

# Example

```python
from huggingface_hub import model_info

info = model_info("meta-llama/Llama-3-70B")
```

---

# Core Formula

## Weight Memory

```txt
weight_memory = (embedding_params + total_attention_params + total_ffn_params) * bytes_per_param
```

- **MoE Support:** Includes all experts in VRAM (routed + shared).
- **GQA Support:** Accounts for reduced Key/Value head parameters.

---

## KV Cache

```txt
kv_cache = 2 * batch * seq_len * num_layers * num_kv_heads * head_dim * bytes_per_element
```

---

## Total VRAM Requirement

```txt
total_vram = (weight_memory + kv_cache) * fragmentation_multiplier + activation_memory + framework_overhead
```

---

# Runtime-Aware Estimation

Need profiles for:
- transformers
- vllm
- llama.cpp

---

# Example Runtime Profile

```json
{
  "runtime": "vllm",

  "kv_overhead_multiplier": 1.2,

  "fragmentation_multiplier": 1.15
}
```

---

# Future Goal — Compatibility Verification System

Future versions MAY include:
- Docker sandbox verification
- runtime reproduction
- crowd-sourced incompatibility confirmation
- automatic runtime validation

However:

## THIS IS NOT REQUIRED FOR MVP

The MVP should work entirely from:
- static metadata
- curated intelligence
- community-managed compatibility rules
- stable stack recommendations

---

# Core Product Insight

The real moat is NOT:
- dependency resolution

The real moat IS:
- accumulated ecosystem intelligence
- operational compatibility knowledge
- stable stack recommendations
- runtime compatibility understanding

The database becomes:
```txt
the memory of the ecosystem
```
