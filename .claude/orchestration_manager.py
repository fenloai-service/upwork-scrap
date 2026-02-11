#!/usr/bin/env python3
"""
Orchestration Manager for WORKFLOW.md implementation.

This script manages the step-by-step implementation workflow defined in
docs/WORKFLOW.md and tracked in .claude/orchestration.json.

Usage:
    python .claude/orchestration_manager.py status          # Show current status
    python .claude/orchestration_manager.py next            # Show next pending step
    python .claude/orchestration_manager.py complete <id>   # Mark step as completed
    python .claude/orchestration_manager.py verify <id>     # Run verification for step
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

ORCHESTRATION_FILE = Path(__file__).parent / "orchestration.json"
WORKFLOW_FILE = Path(__file__).parent.parent / "docs" / "WORKFLOW.md"


def load_orchestration():
    """Load orchestration data from JSON file."""
    with open(ORCHESTRATION_FILE) as f:
        return json.load(f)


def save_orchestration(data):
    """Save orchestration data to JSON file."""
    data["metadata"]["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(ORCHESTRATION_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_all_steps(data):
    """Get all steps from all phases as a flat list."""
    all_steps = []
    for phase in data["phases"]:
        for step in phase["steps"]:
            step["phase_id"] = phase["id"]
            step["phase_name"] = phase["name"]
            all_steps.append(step)
    return all_steps


def find_step_by_id(data, step_id):
    """Find a step by its ID."""
    for step in get_all_steps(data):
        if step["id"] == step_id:
            return step
    return None


def get_next_pending_step(data):
    """Find the first pending step that's not blocked."""
    for phase in data["phases"]:
        # Skip blocked phases
        if phase.get("status") == "blocked":
            continue

        for step in phase["steps"]:
            if step["status"] == "pending":
                return step
    return None


def get_completed_count(data):
    """Count completed steps."""
    all_steps = get_all_steps(data)
    return sum(1 for s in all_steps if s["status"] == "completed")


def get_total_count(data):
    """Count total steps (excluding gates)."""
    all_steps = get_all_steps(data)
    return sum(1 for s in all_steps if not s.get("blocking", False))


def show_status(data):
    """Display current workflow status."""
    print("\n" + "="*70)
    print("📋 ORCHESTRATION STATUS")
    print("="*70)

    completed = get_completed_count(data)
    total = get_total_count(data)
    progress = (completed / total * 100) if total > 0 else 0

    print(f"\n📊 Overall Progress: {completed}/{total} steps ({progress:.1f}%)")
    print(f"📅 Last Updated: {data['metadata']['last_updated']}")
    print(f"🎯 Current Phase: {data['metadata']['current_phase']}")

    for phase in data["phases"]:
        print(f"\n{'='*70}")
        print(f"Phase: {phase['name']}")
        print(f"Status: {phase['status'].upper()}")
        print(f"Estimated: {phase['estimated_hours']}h")
        if phase.get("blocked_by"):
            print(f"⚠️  Blocked by: {phase['blocked_by']}")
        print(f"{'='*70}")

        for step in phase["steps"]:
            status_icon = "✅" if step["status"] == "completed" else "⏳" if step["status"] == "in_progress" else "⬜"
            blocking = " 🚧 [GATE]" if step.get("blocking") else ""
            print(f"  {status_icon} {step['id']} - {step['name']} ({step.get('estimated_hours', 0)}h){blocking}")

    print("\n" + "="*70)


def show_next_step(data):
    """Display the next pending step."""
    next_step = get_next_pending_step(data)

    if not next_step:
        print("\n🎉 All steps completed!")
        return

    print("\n" + "="*70)
    print("📌 NEXT STEP TO IMPLEMENT")
    print("="*70)
    print(f"\nID: {next_step['id']}")
    print(f"Name: {next_step['name']}")
    print(f"Phase: {next_step.get('phase_name', 'Unknown')}")
    print(f"Estimated Time: {next_step.get('estimated_hours', 0)} hours")
    print(f"\nDescription:")
    print(f"  {next_step['description']}")

    if next_step.get("tasks"):
        print(f"\nTasks:")
        for i, task in enumerate(next_step["tasks"], 1):
            print(f"  {i}. {task}")

    if next_step.get("files_to_edit"):
        print(f"\nFiles to Edit:")
        for f in next_step["files_to_edit"]:
            print(f"  - {f}")

    if next_step.get("files_to_create"):
        print(f"\nFiles to Create:")
        for f in next_step["files_to_create"]:
            print(f"  - {f}")

    if next_step.get("verification"):
        print(f"\nVerification Commands:")
        for cmd in next_step["verification"]:
            print(f"  $ {cmd}")

    print("\n" + "="*70)
    print(f"\n💡 To mark complete: python {__file__} complete {next_step['id']}")
    print(f"💡 To verify: python {__file__} verify {next_step['id']}\n")


def verify_step(data, step_id):
    """Run verification commands for a step."""
    step = find_step_by_id(data, step_id)

    if not step:
        print(f"❌ Step {step_id} not found")
        return False

    verification_cmds = step.get("verification", [])

    if not verification_cmds:
        print(f"⚠️  No verification commands defined for step {step_id}")
        return True

    print(f"\n🔍 Verifying step {step_id}: {step['name']}")
    print("="*70)

    all_passed = True
    for cmd in verification_cmds:
        if cmd.startswith("#"):
            print(f"\n📝 Manual check: {cmd}")
            continue

        print(f"\n$ {cmd}")
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                print(f"✅ PASSED")
                if result.stdout:
                    print(f"   Output: {result.stdout.strip()[:100]}")
            else:
                print(f"❌ FAILED (exit code {result.returncode})")
                if result.stderr:
                    print(f"   Error: {result.stderr.strip()[:200]}")
                all_passed = False
        except subprocess.TimeoutExpired:
            print(f"❌ TIMEOUT")
            all_passed = False
        except Exception as e:
            print(f"❌ ERROR: {e}")
            all_passed = False

    print("\n" + "="*70)
    if all_passed:
        print(f"✅ All verifications passed for step {step_id}")
    else:
        print(f"❌ Some verifications failed for step {step_id}")

    return all_passed


def mark_complete(data, step_id):
    """Mark a step as completed."""
    # Find and update the step in the original data structure
    for phase in data["phases"]:
        for step in phase["steps"]:
            if step["id"] == step_id:
                step["status"] = "completed"

                # Update phase status if all steps complete
                all_complete = all(s["status"] == "completed" for s in phase["steps"])
                if all_complete:
                    phase["status"] = "completed"

                    # Unblock next phase if this was a blocker
                    for p in data["phases"]:
                        if p.get("blocked_by") == phase["id"]:
                            p["status"] = "pending"

                save_orchestration(data)
                print(f"✅ Marked step {step_id} as completed")
                return True

    print(f"❌ Step {step_id} not found")
    return False


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    data = load_orchestration()

    if command == "status":
        show_status(data)

    elif command == "next":
        show_next_step(data)

    elif command == "complete":
        if len(sys.argv) < 3:
            print("Usage: python orchestration_manager.py complete <step_id>")
            sys.exit(1)
        step_id = sys.argv[2]
        mark_complete(data, step_id)

    elif command == "verify":
        if len(sys.argv) < 3:
            print("Usage: python orchestration_manager.py verify <step_id>")
            sys.exit(1)
        step_id = sys.argv[2]
        verify_step(data, step_id)

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
