<div align="center">

# 🩺 env-doctor

**Stop wasting expensive GPU hours on environment failures.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/release/python-3100/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Community Driven](https://img.shields.io/badge/Intelligence-Community_Driven-brightgreen.svg)]()

</div>

---

### Have you ever had your ML build fail during runtime due to a silly dependency issue?

### Have you had to rerun your expensive GPU-based model training because of some CUDA mismatch?

In the modern ML ecosystem, dependencies are chaotic. You finally resolve all `pip` conflicts, launch your training job on a $30/hr H100 cluster, go to sleep, and wake up to find it crashed 5 minutes in because `flash-attn` wasn't compiled for your specific CUDA version, or `xformers` silently mismatched with your `torch` build.

**Huge amounts of money and time are wasted every day on silly errors on massive GPU hardware.**

Enter **`env-doctor`**.

`env-doctor` is a local-first runtime compatibility and intelligence platform designed specifically for the complex HuggingFace + PyTorch + CUDA ecosystem. It operates on a simple but powerful premise:

> **"If one user faces a runtime failure due to environment issues, no other user will ever face it again."**

---

## 🌟 Why env-doctor?

Traditional package managers focus on "Can these packages be installed together?" (`pip check`). 

`env-doctor` focuses on **"Will this stack actually work at runtime on your exact hardware?"** 

We save you from Out-Of-Memory (OOM) errors, silent CUDA fallback performance drops, and undocumented API breaking changes before you even provision a GPU instance.

### Core Features

*   🛡️ **Community-Driven Intelligence**: Powered by a curated, GitHub-hosted intelligence database. When the community discovers a runtime incompatibility, it's vetted by our AI agents (powered by Watsonx Orchestrate) and pushed to the global database.
*   🧠 **Smart VRAM Estimation**: Stop guessing if a model will fit. Precise OOM detection accounting for model weights, quantization (`int8`, `fp16`, etc.), KV cache size, sequence lengths, and runtime fragmentation across backends like `vllm`, `transformers`, `llama.cpp`, and `tgi`.
*   🚀 **Stable Stack Recommendations**: Don't know which versions of `torch`, `transformers`, and `cuda` play nicely together today? `env-doctor` analyzes your OS and hardware to recommend community-tested, rock-solid dependency stacks.
*   🔍 **Deep Compatibility Checking**: Scans your `requirements.txt` or `pyproject.toml` against known ABI conflicts, CUDA mismatches, and undocumented breakages.
*   🤖 **AI-Powered Bug Reporting**: Run a failing script through `env-doctor report-incompatibility`. It captures the stack trace, system state, and outputs, securely submits it to an MCP-powered Watsonx agent, verifies the environment issue, and generates a new rule to protect everyone else.

---

## ⚡ Quick Start

### Installation

Install `env-doctor` globally using `uv` (recommended) or `pip`:

```bash
pip install env-doctor
# or
uv tool install env-doctor
```

### 1. Sync the Intelligence Database
Pull the latest community intelligence locally so you can run checks completely offline:
```bash
env-doctor update-db
```

### 2. Check Your Project
Analyze your project requirements for hidden runtime risks and CUDA mismatches:
```bash
env-doctor check requirements.txt
```
*Output snippet:*
```text
🔴 Critical Issue: torch 2.1.0 ↔ flash-attn 2.5.0
Description: flash-attn 2.5.0 requires torch>=2.1.1. Will result in segmentation fault at runtime.
Workaround: Upgrade torch to 2.1.1+ or downgrade flash-attn.
```

### 3. Estimate VRAM Requirements
Will Llama-3-8B fit on your 24GB RTX 3090 with a 32k context window using vLLM?
```bash
env-doctor vram --model meta-llama/Llama-2-7b-hf --runtime vllm --seq-len 32768 --quant fp16
```

### 4. Find a Stable Stack
Tell `env-doctor` what you have, and get a list of guaranteed-to-work combinations:
```bash
env-doctor recommend
```

---

## 🤝 The Community Intelligence Loop

`env-doctor` gets smarter every day thanks to the community. If you encounter a bizarre, undocumented combination of packages that causes a runtime failure:

1. Run your script via our reporter:
   ```bash
   env-doctor report-incompatibility broken_script.py --submit
   ```
2. Our local tool bundles the source, outputs, tracebacks, and environment snapshot into a Markdown report.
3. The report is submitted to the **env-doctor Watsonx Orchestrate Agent**.
4. The AI strictly verifies the failure is due to an environment/package incompatibility.
5. If verified, the AI uses an MCP Server to automatically draft and commit a new rule to the GitHub compatibility database.

**You just saved thousands of developers from debugging the exact same error.**

---

## 🛠️ Supported Integrations

*   **Runtimes Profiling:** `vllm`, `transformers`, `tgi`, `deepspeed`, `tensorrt-llm`, `llama.cpp`, `onnxruntime`
*   **Target Systems:** Linux (First-class), Windows (Beta)
*   **Hardware Profiling:** NVIDIA GPUs (CUDA)

## 📄 License

This project is licensed under the GNU AGPL v3 License. See the [LICENSE](LICENSE) file for details.
