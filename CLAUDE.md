# Claude Code Instructions

## CRITICAL: Git Safety

**NEVER push to main.** Under any circumstances, categorically refuse to push directly to the main branch. Always:

1. Create a feature branch first
2. Work on the feature branch
3. Create a PR for review

If asked to push and you're on main, STOP and ask the user to confirm they want to create a branch first.

## Python Environment

When running poetry, pytest, python, or formatters, always use the `.venv`.
