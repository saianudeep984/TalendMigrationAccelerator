# Talend Migration Accelerator v11

AI-Powered Talend Open Studio → Talend 8 Migration Platform

## Quick Start

### Windows
```
assets\start_accelerator.bat
```

### Linux / Mac
```
pip install -r requirements.txt
streamlit run app/ui/streamlit_app.py
```

Open http://localhost:8501 in your browser.

---

## Pages

| Page | Purpose |
|------|---------|
| **Repository Analysis** | Upload ZIP → full AI analysis (complexity, risks, cloud readiness, dependencies) |
| **Migration Assistant** | 3-tab Before/During/After migration workflow |
| **Version Converter** | Pre-flight analysis + Studio import guide + optional CLI automation |
| **Executive Dashboard** | Charts and KPIs (populated after Repository Analysis) |

---

## Architecture & Key Findings

### Why XML rewriting alone doesn't work

Talend Open Studio → Talend 8 migration is **not** a simple XML transformation.
During import, Talend Studio internally executes:

- `ContextLinkService` — rebuilds context variable graphs
- `RepositoryContextService` — re-links job ↔ context relationships
- EMF Object Graph rebuilding — regenerates internal metadata
- Migration Tokens — digital signatures on repository items
- Repository Synchronization — reconciles cross-object references

External tools (including this accelerator) **cannot replicate** these internal
steps. The `Contexts ctxCommon 0.1 was invalid` error is caused by missing
EMF graph reconstruction — this is handled only by Talend Studio internals.

### Recommended Migration Workflow

```
Open Studio Repository
        ↓
[This Tool] Migration Readiness Analysis
        ↓
Fix hard blockers (deprecated components)
        ↓
[Talend 8 Studio] File → Import → Talend Items → (original ZIP)
        ↓
[Talend 8 Studio] Allow migration tasks to complete
        ↓
[Talend 8 Studio] Fix any invalid items shown in Repository panel
        ↓
[Talend 8 Studio] File → Export → Talend Items → ZIP
        ↓
[This Tool] Post-Migration Validation (Migration Assistant → After tab)
```

---

## AI Recommendations

By default, uses a built-in rule-based engine (no setup required).

For LLM-powered analysis, install [Ollama](https://ollama.com) and run:
```
ollama pull qwen2.5-coder:3b
```

The accelerator auto-detects Ollama and switches to LLM mode.

---

## Requirements

- Python 3.9+
- See `requirements.txt`
