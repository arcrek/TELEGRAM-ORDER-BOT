# Skill: Conventional Git Commit

## Goal
Create clean, standardized git commit messages following the Conventional Commits specification.

## When to use
- After making code changes
- Before pushing to remote
- When user says: "commit", "create commit", "commit changes"

## Instructions

1. Analyze staged changes:
   - Run: `git diff --staged`
   - If nothing staged → run `git add .`

2. Understand the change:
   - Identify type:
     - feat: new feature
     - fix: bug fix
     - docs: documentation only
     - style: formatting, no logic change
     - refactor: code change without feature/fix
     - perf: performance improvement
     - test: add/update tests
     - chore: maintenance

3. Determine scope (optional):
   - Example: auth, api, db, ui, config

4. Generate commit message:

Format:
<type>(<scope>): <short summary>
[optional body]
[optional footer]


Rules:
- summary ≤ 72 chars
- use lowercase
- no trailing period
- imperative mood (e.g., "add", not "added")

5. Examples:
- `feat(auth): add JWT login support`
- `fix(api): handle null response in user endpoint`
- `chore(deps): update sqlalchemy version`

6. Execute commit:
   - `git commit -m "<message>"`

## Advanced behavior

- If multiple logical changes → suggest splitting commits
- If breaking change:
  - add `!` after type
  - include `BREAKING CHANGE:` in footer

Example:

feat(api)!: change user response format

BREAKING CHANGE: response no longer includes legacy fields


## Output format

Return ONLY:
- the final commit message
- and executed command

No explanation unless asked

## Commit Decision Logic

1. Check staged changes:
   - `git diff --staged --quiet`

2. If NOTHING is staged:
   - Check untracked files:
     - `git ls-files --others --exclude-standard`

3. Behavior:

### Case A: staged changes exist
→ Generate conventional commit normally

### Case B: only untracked files exist

- If files are inside `.claude/`:
  → Auto stage them
  → Use:
    `chore(claude): add/update claude skills`

- Otherwise:
  → Ask user:
    "No staged changes. Do you want me to commit all untracked files?"

### Case C: nothing to commit
→ Output:
  "Nothing to commit"