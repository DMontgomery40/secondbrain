name: conventional-commits-enforcer
description: Enforces conventional commit message format (feat/fix/docs/chore/refactor/test/perf/ci/build/revert) for all git commits. Use when creating commits, reviewing commit messages, or discussing version control.
allowed-tools: 
  - Bash(git status:*)
  - Bash(git diff:*)
  - Bash(git add:*)
  - Bash(git commit:*)
  - Bash(git log:*)
---

# Conventional Commits Enforcer

## CRITICAL RULES - ALWAYS ENFORCED

Every git commit message MUST follow this EXACT format:
```
<type>: <description>

[optional body]

[optional footer]
```

### Valid Types (ONLY these are allowed):
- `feat:` - New feature for the user
- `fix:` - Bug fix
- `docs:` - Documentation only changes
- `style:` - Formatting, missing semi colons, etc; no code change
- `refactor:` - Refactoring production code
- `test:` - Adding tests, refactoring test; no production code change  
- `chore:` - Updating build tasks, package manager configs, etc; no production code change
- `perf:` - Performance improvements
- `ci:` - CI/CD changes
- `build:` - Build system changes
- `revert:` - Reverts a previous commit

### Format Rules (MUST follow ALL):
1. Type MUST be lowercase
2. Colon MUST come immediately after type (no space before colon)
3. Single space MUST come after colon
4. Description MUST start with lowercase letter
5. Description MUST be in imperative mood ("add" not "added" or "adds")
6. Description MUST NOT end with a period
7. First line MUST be 72 characters or less
8. Body and footer are optional but MUST be separated by blank lines

### Examples of CORRECT commits:
```
feat: add user authentication
fix: resolve memory leak in database connection
docs: update README with installation steps
refactor: simplify error handling logic
test: add unit tests for auth module
chore: update dependencies to latest versions
```

### Examples of INCORRECT commits (NEVER allow these):
```
✗ Add user authentication (missing type)
✗ FEAT: add login (type must be lowercase)
✗ feat : add login (space before colon)  
✗ feat:add login (missing space after colon)
✗ feat: Add login (description must start lowercase)
✗ feat: added login (must be imperative mood)
✗ feat: add login. (no period at end)
✗ feature: add login (invalid type - must be "feat")
```

## Instructions

When I ask you to commit changes or create a commit message:

1. **Check staged changes**: Run `git diff --staged` to see what's being committed
2. **Validate format**: Ensure the commit message follows ALL rules above
3. **Reject invalid formats**: If I provide an invalid format, explain what's wrong and provide the correct format
4. **Generate proper messages**: When creating commit messages, always use conventional format
5. **Explain your choice**: Briefly explain which type you chose and why

## Auto-Versioning Context

This project uses conventional commits for automatic semantic versioning:
- `feat:` commits trigger MINOR version bumps (0.X.0)
- `fix:` commits trigger PATCH version bumps (0.0.X)  
- `BREAKING CHANGE:` in footer triggers MAJOR version bumps (X.0.0)

Therefore, choosing the correct type is CRITICAL for proper versioning.

## When NOT to use this Skill

- When discussing version numbers (that's versioning, not committing)
- When reviewing code (unless specifically about commit messages)
- When writing documentation (unless it's about git workflow)
EOF

# Create the /commit slash command
cat > "$PLUGIN_DIR/commands/commit.md" << 'EOF'
---
description: "Analyze changes and create a conventional commit with proper format"
allowed-tools:
  - Bash(git status:*)
  - Bash(git diff:*)
  - Bash(git add:*)
  - Bash(git commit:*)
  - Bash(git log:*)
---

# Commit Command

## Context (auto-collected)

- Current branch: !`git branch --show-current`
- Git status: !`git status --porcelain`
- Staged changes: !`git diff --cached`
- Unstaged changes: !`git diff`
- Recent commits: !`git log --oneline -5`

## Task

1. Analyze the changes shown above
2. Determine the appropriate conventional commit type (feat/fix/docs/etc)
3. Generate a commit message following conventional commits format
4. Show me the proposed message and ask for confirmation
5. If I approve, stage all changes with `git add -A` and commit

## Format Requirements

The commit message MUST follow this format:
```
<type>: <description>
```

Valid types: feat, fix, docs, style, refactor, test, chore, perf, ci, build, revert

Rules:
- Type must be lowercase
- Colon immediately after type
- Single space after colon
- Description starts with lowercase
- Imperative mood ("add" not "added")
- No period at end
- First line ≤72 characters

## Example Output

After analysis, present:
```
Proposed commit message:
feat: add email validation to registration form

This commit adds:
- Email format validation
- Duplicate email checking
- Error messages for invalid emails

Type: feat (new feature for users)
```

Then ask: "Does this commit message look good? (yes/no)"

If yes, execute:
1. `git add -A`
2. `git commit -m "<approved message>"`
3. Show commit hash and success message