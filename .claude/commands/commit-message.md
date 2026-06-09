# Commit Message

Generate a short, accurate git commit message for the work done this session.

Steps:
1. Run `git diff --staged` and `git diff` to see all changed and staged files.
2. Run `git status` to identify any untracked new files.
3. Review what changed across all modified files.
4. Output a single commit message line in this format: `STO-XX: brief description of what changed`
   - Infer the STO issue number from the file paths or names of changed files (e.g. `app/main.py` → STO-04, `analysis/indicators.py` → STO-03).
   - If multiple issues are touched, list the primary one.
   - Keep it under 72 characters.
   - Use active voice: "add", "fix", "update", "remove" — not "added" or "adding".
   - Describe the *what*, not the *how*.

Output only the commit message string. No explanation, no extra text.
