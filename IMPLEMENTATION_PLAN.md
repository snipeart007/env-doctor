# env-doctor — Comprehensive Implementation Plan

## Executive Summary

This implementation plan provides a detailed roadmap for building `env-doctor`, a local-first runtime compatibility intelligence and VRAM analysis tool for the HuggingFace + Torch + CUDA ecosystem.

**Project Duration:** 16-20 weeks for MVP  
**Team Size:** 2-4 developers  
**Critical Path:** Database Schema → Metadata Collection → CLI Engine → Compatibility Analysis

---

## Project Overview

### Vision
`env-doctor` solves undocumented runtime incompatibilities, CUDA/toolchain mismatches, unstable package combinations, and VRAM estimation inaccuracies in the ML ecosystem.

### Core Components
1. **Community Database Repository** - GitHub-hosted compatibility intelligence
2. **Local CLI Engine** - Offline-capable analysis tool
3. **Automatic Metadata System** - PyPI-based data collection
4. **Compatibility Engine** - Rule-based analysis
5. **Recommendation System** - Stable stack suggestions
6. **VRAM Estimator** - Memory requirement calculator
7. **Reporting System** - AI-powered incompatibility detection

### Product Philosophy
- **Local-first**: All analysis runs locally
- **Community-driven**: Database maintained by users
- **Intelligence over resolution**: Focus on "will it work?" not "can pip install it?"
- **Two-layer system**: Automatic metadata + curated intelligence

---

## Implementation Phases

### Phase 1: Project Foundation (1-2 weeks)

**Objectives:** Establish infrastructure, tooling, and project structure

**Key Deliverables:**
- Main repository (`env-doctor`) with CI/CD
- Database repository (`env-doctor-db`) with validation
- Development environment with `uv`, `ruff`, `mypy`, `pytest`
- Project structure following specification
- GitHub Actions workflows

**Critical Tasks:**
1. Initialize both repositories with proper governance
2. Configure `pyproject.toml` with dependencies (typer, rich, pydantic, httpx, packaging, sqlmodel)
3. Set up CI/CD for testing (Python 3.10, 3.11, 3.12)
4. Create project directory structure
5. Configure development tools (ruff, mypy, pre-commit)

**Acceptance Criteria:**
- Repositories accessible and configured
- CI/CD pipelines passing
- Development environment reproducible
- Team can start development

---

### Phase 2: Database Schema & Compiler (2-3 weeks)

**Objectives:** Implement SQLite schema, UID system, YAML compiler, and validation

**Key Deliverables:**
- Complete SQLite schema with 8 tables
- Deterministic SHA-256 UID generation
- YAML-to-SQLite compiler
- Data validation framework
- Database manager with query API

**Database Tables:**
1. `packages` - Package registry
2. `package_versions` - Version tracking
3. `package_dependencies` - Auto-generated from PyPI
4. `compatibility_rules` - Curated intelligence
5. `stable_stacks` - Recommended combinations
6. `stable_stack_packages` - Stack composition
7. `wheel_availability` - Platform wheels
8. `runtime_profiles` - Runtime overhead data

**UID Generation Functions:**
```python
generate_package_uid(name)
generate_version_uid(name, version)
generate_dependency_uid(pkg, ver, dep)
generate_compatibility_uid(pkg, pkg_range, dep, dep_range, cuda_ver=None, env_sys=None)
generate_stack_uid(name, cuda_ver, env_sys=None)
generate_wheel_uid(pkg, ver, py_tag, platform_tag)
generate_runtime_uid(runtime)
```

**YAML Compiler Workflow:**
1. Fetch YAML files from GitHub
2. Validate structure and content
3. Generate deterministic UIDs
4. Insert/update database records
5. Update metadata
6. Commit transaction

**Acceptance Criteria:**
- Schema creates all tables with proper constraints
- UIDs deterministic and collision-free
- Compiler processes YAML files correctly
- Validation prevents invalid data
- Performance acceptable (<30s for 50 packages)

---

### Phase 3: Metadata Collection System (2-3 weeks)

**Objectives:** Implement PyPI integration and automatic database population

**Key Deliverables:**
- PyPI API client with caching
- Dependency parser using `packaging` library
- Wheel metadata extractor
- Database bootstrap system
- Two-layer intelligence integration

**PyPI Integration:**
- Endpoint: `https://pypi.org/pypi/{package}/json`
- Cache location: `~/.cache/env-doctor/pypi/`
- Cache TTL: 24 hours
- Rate limiting and retry logic

**Data Extraction:**
- `requires_dist` → package_dependencies table
- `requires_python` → Python version constraints
- `releases` → wheel_availability table
- Version metadata → package_versions table

**Bootstrap Process:**
```
Package List (torch, transformers, etc.)
    ↓
Fetch PyPI Metadata (parallel)
    ↓
Parse Dependencies & Constraints
    ↓
Extract Wheel Metadata
    ↓
Populate Database (Layer 1)
    ↓
Apply Curated Rules (Layer 2)
```

**Two-Layer System:**
- **Layer 1 (Automatic):** PyPI metadata - declared compatibility
- **Layer 2 (Curated):** YAML rules - operational compatibility

**Acceptance Criteria:**
- PyPI client fetches metadata reliably
- Dependencies parsed correctly
- Wheel availability tracked
- Bootstrap populates all tables
- Two layers integrated properly

---

### Phase 4: CLI Engine (2 weeks)

**Objectives:** Build CLI interface with all commands

**Key Deliverables:**
- Typer-based CLI framework
- 7 core commands implemented
- Rich terminal UI
- Configuration system
- Help documentation

**Commands:**

1. **`env-doctor update-db`**
   - Download YAML from GitHub
   - Compile to SQLite
   - Show progress and statistics

2. **`env-doctor inspect`**
   - Scan current environment
   - Detect Python, CUDA, GPU
   - List installed packages

3. **`env-doctor check <requirements.txt>`**
   - Parse requirements
   - Check compatibility rules
   - Show conflicts and warnings

4. **`env-doctor recommend`**
   - Analyze environment
   - Find matching stable stacks
   - Suggest best option

5. **`env-doctor vram --model <model> --runtime <runtime> --quant <quant>`**
   - Fetch model info
   - Calculate VRAM requirements
   - Show breakdown and warnings

6. **`env-doctor patch <pyproject.toml|requirements.txt>`**
   - Detect incompatibilities
   - Suggest fixes
   - Apply patches with confirmation

7. **`env-doctor report-incompatibility <script.py|notebook.ipynb>`**
   - Execute locally
   - Capture output
   - Submit for analysis

**Rich UI Components:**
- Progress bars
- Tables for data
- Panels for grouping
- Syntax highlighting
- Color-coded severity
- Interactive prompts

**Configuration:**
- Location: `~/.config/env-doctor/config.toml`
- Settings: auto_update, cache_dir, verbosity
- Environment variable overrides

**Acceptance Criteria:**
- All commands functional
- UI provides excellent UX
- Configuration works
- Help system comprehensive
- Error handling robust

---

### Phase 5: Compatibility Analysis Engine (2-3 weeks)

**Objectives:** Implement compatibility checking and conflict detection

**Key Deliverables:**
- Version range matching engine
- Compatibility rule matcher
- Dependency graph analyzer
- Conflict detector
- Severity scoring system
- Report generator

**Version Matching:**
```python
from packaging.specifiers import SpecifierSet
from packaging.version import Version

def version_matches(version: str, specifier: str) -> bool:
    return Version(version) in SpecifierSet(specifier)
```

**Compatibility Types:**
- `compatible` - Explicitly compatible
- `incompatible` - Known to break
- `partial` - Works with limitations
- `runtime-risk` - May fail at runtime
- `untested` - No community data

**Conflict Detection:**
- Version conflicts (unsatisfiable constraints)
- Runtime conflicts (known broken combinations)
- ABI conflicts (CUDA version mismatches)

**Severity Scoring:**
- Critical: 100 (will definitely break)
- High: 75 (very likely to break)
- Medium: 50 (may break)
- Low: 25 (minor issues)
- Info: 0 (informational)

**Confidence Weighting:**
- Production-tested: 1.0x
- Stable: 0.9x
- Community-tested: 0.7x
- Experimental: 0.5x

**Report Sections:**
1. Summary - Overall status
2. Critical Issues - Must fix
3. Warnings - Should fix
4. Recommendations - Suggested actions
5. Details - Full analysis

**Acceptance Criteria:**
- Version matching handles all cases
- Rules matched correctly
- Conflicts detected reliably
- Severity scoring reasonable
- Reports clear and actionable

---

### Phase 6: Recommendation Engine (2 weeks)

**Objectives:** Implement stable stack matching and recommendations

**Key Deliverables:**
- Stack matching algorithm
- Recommendation scoring
- Migration path generator
- Ranking system
- Interactive selection UI

**Matching Criteria:**
- CUDA version compatibility
- Python version compatibility
- Package overlap with current environment
- Platform compatibility

**Scoring Factors:**
- Confidence level (40%)
- Package overlap (30%)
- Recency (20%)
- Community adoption (10%)

**Migration Path:**
1. Identify packages to upgrade/downgrade
2. Identify packages to add/remove
3. Order by dependencies
4. Generate installation commands

**Example Output:**
```bash
# Recommended: torch-2.1-transformers-4.38 (Score: 95)

# Step 1: Upgrade torch
pip install torch==2.1.0+cu118 --index-url https://...

# Step 2: Upgrade transformers
pip install transformers==4.38.0

# Step 3: Install flash-attn
pip install flash-attn==2.5.0
```

**Acceptance Criteria:**
- Stack matching finds relevant stacks
- Scoring produces reasonable rankings
- Migration paths correct
- UI intuitive
- Recommendations actionable

---

### Phase 7: VRAM Intelligence Engine (2-3 weeks)

**Objectives:** Implement VRAM estimation and OOM detection

**Key Deliverables:**
- Model info fetcher (HuggingFace Hub)
- Weight memory calculator
- KV cache estimator
- Runtime profile system
- OOM risk detector

**Weight Memory Formula:**
```
weight_memory = (embedding_params + total_attention_params + total_ffn_params) * bytes_per_param
```
- **MoE Support:** `total_ffn_params = num_layers * (num_experts * ffn_params_per_expert + shared_expert_params)`
- **GQA Support:** `attention_params` adjusted for reduced KV heads.

**KV Cache Formula:**
```
kv_cache = 2 * batch * seq_len * num_layers * num_kv_heads * head_dim * bytes_per_element
```
- `head_dim = hidden_size / num_attention_heads`
- `num_kv_heads` = `num_attention_heads` (MHA) or reduced count (GQA/MQA)

**Total VRAM Estimate:**
```
total_vram = (weight_memory + kv_cache) * fragmentation_multiplier + activation_memory + framework_overhead
```
- **Fragmentation:** Typically 1.1x - 1.2x
- **Framework Overhead:** ~0.5GB - 1.5GB (PyTorch/CUDA context)
- **Activation Memory:** `batch * seq_len * hidden * num_layers * (approx_factor)`

**Runtime Profiles:**
```python
{
  "transformers": {
    "kv_overhead_multiplier": 1.0,
    "fragmentation_multiplier": 1.2
  },
  "vllm": {
    "kv_overhead_multiplier": 1.1,
    "fragmentation_multiplier": 1.15
  }
}
```

**OOM Risk Levels:**
- Safe: <70% VRAM
- Warning: 70-85% VRAM
- Danger: 85-95% VRAM
- Critical: >95% VRAM

**Acceptance Criteria:**
- Model info fetched correctly
- Calculations accurate
- Runtime profiles applied
- OOM risks detected
- UI clear and helpful

---

### Phase 8: Incompatibility Reporting (2-3 weeks)

**Objectives:** Implement error reporting and AI analysis via Watsonx Orchestrate

**Key Deliverables:**
- Script/notebook execution system (cell-by-cell for notebooks)
- Markdown report generator (Code + Output + Env Info)
- Watsonx Orchestrate submission placeholder
- Python MCP Server for GitHub database updates
- Strict verification logic in AI agent prompt
- Setup guide for Watsonx agent

**Execution:**
- Python scripts: Full source capture and execution via `subprocess.run()`.
- Jupyter notebooks: Programmatic execution via `nbclient` to capture outputs cell-by-cell.
- Capture: Source code, stdout, stderr, and full environment manifest.

**Markdown Report Format:**
- `## Python Code` or `## Cell [X]` sections for source.
- `## Output` sections for execution results and tracebacks.
- `## Environment Info` section with JSON snapshot of the system.

**Watsonx Orchestrate Workflow:**
1. Execute script/notebook locally.
2. Generate comprehensive Markdown report.
3. Submit Markdown to Watsonx Orchestrate agent.
4. AI Agent performs **Strict Verification**: Rejects any error not caused by environment/package incompatibility.
5. If verified, AI Agent generates structured compatibility JSON.
6. AI Agent calls **MCP Server** tool (`update_compatibility_database`) to commit YAML to GitHub.

**MCP Server:**
- FastMCP-based Python server.
- Tool: `update_compatibility_database` (updates GitHub repository).
- Authentication: `GITHUB_API_KEY` environment variable.

**Acceptance Criteria:**
- Notebooks executed cell-by-cell.
- Markdown reports generated correctly.
- MCP server functional and secure.
- Strict verification logic enforced.
- Documentation for setup complete.

---

### Phase 9: Testing & QA (2 weeks, parallel)

**Objectives:** Comprehensive testing and quality assurance

**Key Deliverables:**
- Unit test suite (>80% coverage)
- Integration tests
- End-to-end tests
- Performance benchmarks
- Security audit
- User acceptance testing

**Test Coverage:**
- Database operations
- UID generation
- Version matching
- Dependency parsing
- VRAM calculations
- CLI commands
- Compatibility analysis
- Recommendations
- Reporting system

**Performance Benchmarks:**
- Database compilation: <30s for 50 packages
- Compatibility check: <2s for 20 packages
- Recommendation: <5s
- VRAM estimation: <1s
- PyPI fetch: <10s for 10 packages

**Security Testing:**
- SQL injection prevention
- Command injection prevention
- Path traversal prevention
- Dependency vulnerabilities
- Secrets exposure

**Acceptance Criteria:**
- >80% code coverage
- All tests passing
- Benchmarks met
- No critical security issues
- Positive user feedback

---

### Phase 10: Documentation & Community (1-2 weeks)

**Objectives:** Create documentation and community infrastructure

**Key Deliverables:**
- User documentation (MkDocs)
- Developer documentation (Sphinx)
- API reference
- Tutorials and examples
- Contribution guidelines
- Community channels

**User Documentation:**
- Getting Started
- Installation Guide
- CLI Reference (all commands)
- Configuration Guide
- Troubleshooting
- FAQ

**Developer Documentation:**
- Architecture Overview
- Database Schema
- API Reference
- Contributing Guide
- Development Setup
- Testing Guide

**Community Setup:**
- GitHub Discussions
- Issue templates
- PR templates
- Code of Conduct
- Contribution workflow
- Release process

**Tutorials:**
1. Checking environment compatibility
2. Using stable stacks
3. Estimating VRAM requirements
4. Contributing compatibility rules
5. Reporting incompatibilities

**Acceptance Criteria:**
- Documentation complete and clear
- Examples work correctly
- Contribution process documented
- Community channels active

---

### Phase 11: MVP Release (1 week)

**Objectives:** Prepare and execute MVP release

**Key Deliverables:**
- Release candidate testing
- PyPI package publication
- Initial database population
- Release announcement
- Marketing materials

**Pre-Release Checklist:**
- [ ] All tests passing
- [ ] Documentation complete
- [ ] Security audit passed
- [ ] Performance benchmarks met
- [ ] User testing completed
- [ ] Release notes written
- [ ] Migration guide prepared

**Release Process:**
1. Create release branch
2. Final testing round
3. Update version numbers
4. Build distribution packages
5. Publish to PyPI
6. Tag release in Git
7. Create GitHub release
8. Announce on social media

**Initial Database:**
- Populate with 20-30 core packages
- Include 50+ compatibility rules
- Add 5-10 stable stacks
- Document contribution process

**Marketing:**
- Blog post announcement
- Twitter/X thread
- Reddit posts (r/MachineLearning, r/LocalLLaMA)
- HuggingFace community
- Discord/Slack communities

**Acceptance Criteria:**
- Package installable via pip
- Database accessible
- All features functional
- Documentation live
- Community engaged

---

### Phase 12: Post-MVP Enhancements (Ongoing)

**Objectives:** Iterate based on feedback and add features

**Planned Enhancements:**

**Short-term (1-3 months):**
- Windows support
- ROCm support
- Additional package ecosystem coverage
- Enhanced VRAM estimation
- GitHub authentication for reporting
- Improved recommendation algorithm

**Medium-term (3-6 months):**
- Web dashboard for database browsing
- API for programmatic access
- IDE integrations (VS Code extension)
- Automated testing of compatibility rules
- Community voting on rules
- Analytics and usage tracking

**Long-term (6-12 months):**
- Docker sandbox verification
- Distributed training support
- Kubernetes integration
- TensorFlow ecosystem support
- Apple Metal support
- Enterprise features

**Community Growth:**
- Regular database updates
- Community calls
- Contributor recognition
- Documentation improvements
- Tutorial videos
- Conference talks

---

## Project Management

### Critical Path
```
Phase 1 (Foundation)
    ↓
Phase 2 (Database Schema) ← Critical
    ↓
Phase 3 (Metadata Collection) ← Critical
    ↓
Phase 4 (CLI Engine) ← Critical
    ↓
Phase 5 (Compatibility Analysis) ← Critical
    ↓
Phase 6 (Recommendations)
    ↓
Phase 7 (VRAM Estimation)
    ↓
Phase 8 (Reporting)
    ↓
Phase 9 (Testing) - Parallel
    ↓
Phase 10 (Documentation)
    ↓
Phase 11 (Release)
```

### Resource Allocation

**Team Structure:**
- **Lead Developer** - Architecture, critical path
- **Backend Developer** - Database, metadata, analysis
- **Full Stack Developer** - CLI, UI, reporting
- **ML Engineer** - VRAM estimation, AI integration
- **QA Engineer** - Testing, quality assurance
- **Technical Writer** - Documentation

**Time Allocation:**
- Development: 70%
- Testing: 15%
- Documentation: 10%
- Project Management: 5%

### Risk Management

**High-Priority Risks:**

1. **Database Schema Changes**
   - Impact: Critical
   - Mitigation: Thorough design review, migration system

2. **PyPI API Changes**
   - Impact: High
   - Mitigation: Version detection, fallback mechanisms

3. **AI Analysis Accuracy**
   - Impact: High
   - Mitigation: Human review, confidence thresholds

4. **Community Adoption**
   - Impact: High
   - Mitigation: Marketing, documentation, ease of use

5. **Performance Issues**
   - Impact: Medium
   - Mitigation: Benchmarking, optimization, caching

### Success Metrics

**Technical Metrics:**
- Database compilation time: <30s
- Compatibility check time: <2s
- Test coverage: >80%
- Bug count: <10 critical bugs at release

**Adoption Metrics:**
- PyPI downloads: 1000+ in first month
- GitHub stars: 500+ in first 3 months
- Database contributions: 50+ PRs in first 3 months
- Active users: 100+ weekly active users

**Quality Metrics:**
- User satisfaction: >4/5 rating
- Documentation completeness: 100%
- Issue resolution time: <7 days average
- Community engagement: Active discussions

---

## Appendix

### Technology Stack

**Core:**
- Python 3.10+
- SQLite (database)
- uv (package management)
- Typer (CLI framework)
- Rich (terminal UI)

**Libraries:**
- pydantic (validation)
- httpx (HTTP client)
- packaging (version parsing)
- sqlmodel (ORM)
- huggingface_hub (model info)

**Development:**
- pytest (testing)
- ruff (linting/formatting)
- mypy (type checking)
- pre-commit (git hooks)

**Infrastructure:**
- GitHub Actions (CI/CD)
- PyPI (distribution)
- AWS Lambda / Vercel (serverless)
- watsonx (AI analysis)

### File Structure

```
env-doctor/
├── pyproject.toml
├── README.md
├── src/env_doctor/
│   ├── __init__.py
│   ├── main.py
│   ├── cli/
│   │   ├── update.py
│   │   ├── inspect.py
│   │   ├── check.py
│   │   ├── recommend.py
│   │   ├── vram.py
│   │   ├── patch.py
│   │   └── report.py
│   ├── core/
│   │   ├── compatibility.py
│   │   ├── recommendations.py
│   │   └── analysis.py
│   ├── database/
│   │   ├── models.py
│   │   ├── compiler.py
│   │   ├── manager.py
│   │   ├── queries.py
│   │   └── uid_generator.py
│   ├── scanner/
│   │   ├── environment.py
│   │   ├── packages.py
│   │   └── system.py
│   ├── vram/
│   │   ├── estimator.py
│   │   ├── models.py
│   │   └── profiles.py
│   ├── reporting/
│   │   ├── capture.py
│   │   ├── submission.py
│   │   └── analysis.py
│   └── utils/
│       ├── config.py
│       ├── logging.py
│       └── helpers.py
├── tests/
└── docs/
```

### Database Schema Summary

**8 Core Tables:**
1. `packages` - Package registry
2. `package_versions` - Version tracking
3. `package_dependencies` - Dependency graph
4. `compatibility_rules` - Curated rules
5. `stable_stacks` - Recommended stacks
6. `stable_stack_packages` - Stack composition
7. `wheel_availability` - Platform wheels
8. `runtime_profiles` - Runtime overhead

### CLI Commands Summary

1. `update-db` - Update local database
2. `inspect` - Scan environment
3. `check` - Check compatibility
4. `recommend` - Suggest stable stack
5. `vram` - Estimate VRAM
6. `patch` - Fix dependencies
7. `report-incompatibility` - Report errors

---

## Conclusion

This implementation plan provides a comprehensive roadmap for building `env-doctor` from foundation to MVP release. The phased approach ensures systematic progress while maintaining flexibility for iteration based on feedback.

**Key Success Factors:**
- Strong database design (Phase 2)
- Reliable metadata collection (Phase 3)
- Excellent user experience (Phase 4)
- Accurate compatibility analysis (Phase 5)
- Active community engagement (Phase 10-12)

**Next Steps:**
1. Review and approve this plan
2. Assemble development team
3. Begin Phase 1 (Project Foundation)
4. Establish weekly progress reviews
5. Set up communication channels

The estimated 16-20 week timeline to MVP is achievable with a dedicated team of 2-4 developers following this structured approach.