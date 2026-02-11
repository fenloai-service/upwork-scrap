# Claude Code Orchestration System

This directory contains the orchestration system for implementing the proposal automation workflow from `docs/WORKFLOW.md`.

## Files

- **`orchestration.json`** - Structured task list with 3 phases, 16 steps, tracking status and verification
- **`orchestration_manager.py`** - Python CLI tool to view status, get next task, mark complete, and verify steps
- **`README.md`** - This file

## How It Works

When you say **"continue implementation"** to Claude Code, it will:

1. Read `orchestration.json` to find the next pending step
2. Implement that step following the tasks and requirements
3. Run verification commands to confirm completion
4. Update the step status to "completed"
5. Save the updated orchestration file

## Manual Usage

You can also manage the workflow manually:

```bash
# View overall status
python .claude/orchestration_manager.py status

# See the next pending step
python .claude/orchestration_manager.py next

# Verify a step's implementation
python .claude/orchestration_manager.py verify 1.1

# Mark a step as complete
python .claude/orchestration_manager.py complete 1.1
```

## Workflow Phases

### Phase 1: Core Automation Pipeline (26 hours)
1. **1.1** - Config Infrastructure (2h)
2. **1.2** - Proposals Table + DB Functions (3h)
3. **1.3** - Job Preference Matcher (4h)
4. **1.4** - Proposal Generator (4h)
5. **1.5** - Monitor CLI Command (3h)
6. **1.6** - Streamlit Dashboard - Proposals Tab (6h)
7. **1.7** - Unit & Integration Tests (4h)
8. **Gate** - Phase 1 Gate (all tests must pass)

### Phase 2: UX Enhancements (9 hours)
1. **2.1** - Inline Proposal Editing (2h)
2. **2.2** - Copy-to-Clipboard & Status Workflow (2h)
3. **2.3** - Email Notifier (4h)
4. **2.4** - Wire Email into Monitor (1h)

### Phase 3: Production Readiness (9 hours)
1. **3.1** - Streamlit Cloud Deployment Prep (3h)
2. **3.2** - Ollama Fallback (3h)
3. **3.3** - Quality Feedback Loop (3h)

## Current Status

All steps are **pending**. The first step to implement is **1.1 - Config Infrastructure**.

## Integration with Claude Code

Claude Code automatically:
- Reads `orchestration.json` when you say "continue implementation"
- Implements the next pending step
- Runs verification commands
- Updates status and commits changes
- Moves to the next step

## Definition of Done

Every completed step must satisfy:
1. ✅ Code passes `python -m py_compile` for all modified files
2. ✅ No new warnings or errors in `pytest` output
3. ✅ Public functions have docstrings
4. ✅ Config files validate with `yaml.safe_load()`
5. ✅ No secrets or API keys committed
6. ✅ All verification commands pass

## Rollback

Each step has a rollback plan if needed. See `orchestration.json` for step-specific rollback instructions.

## Notes

- Steps must be completed in order (strict sequence)
- Phase 2 is blocked until Phase 1 gate passes
- Phase 3 is blocked until Phase 2 completes
- Each step has estimated time, verification commands, and rollback plan
