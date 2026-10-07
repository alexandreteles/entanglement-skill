# Entanglement skill

Keep code size and complexity under control while a coding agent works.
This skill uses [Entanglement](https://github.com/alexandreteles/entanglement)
to capture a repository baseline, compare subsequent edits, and enforce a
file-level maintainability gate. It supports Rust, Python, Go, TypeScript/TSX,
JavaScript, Svelte, HTML, and CSS.

The workflow is portable: [SKILL.md](SKILL.md) contains the agent instructions,
and [scripts/compare.py](scripts/compare.py) is a standalone comparator.
Any harness with file access and shell execution can follow it. Native skill
discovery and invocation syntax depend on the harness; `agents/openai.yaml`
provides optional Codex UI metadata.

## Requirements

Install these in the environment where your agent executes commands:

- **Entanglement on PATH.** With a stable Rust toolchain, install from source:

  ```sh
  cargo install --git https://github.com/alexandreteles/entanglement --locked entanglement
  ```

  Ensure Cargo's binary directory is on PATH. See the
  [analyzer documentation](https://github.com/alexandreteles/entanglement#build-and-run)
  for build instructions.
- **Python 3.14+**, available as `python3`, for the comparator. It uses only
  Python's standard library.
- **Node.js/npm** if using the `npx skills` installer below; Git for manual cloning.

Verify the runtime separately from installing the skill:

```sh
entanglement --version
python3 --version
```

## Install with Vercel Skills

From your project directory, install for both Claude Code and Codex:

```sh
npx skills add alexandreteles/entanglement-skill --skill entanglement --agent claude-code codex
```

For availability across projects, use global scope:

```sh
npx skills add alexandreteles/entanglement-skill --skill entanglement --agent claude-code codex --global
```

Choose only `--agent claude-code` or `--agent codex` if you use one harness.
Omit `--agent` to choose other supported agents interactively. Add `--copy`
when you want independent copies instead of symlinks, or `--yes` for unattended
installation. These options and agent identifiers are documented by
[vercel-labs/skills](https://github.com/vercel-labs/skills#options).

Preview discovery without installing:

```sh
npx skills add alexandreteles/entanglement-skill --list
```

The repository exposes one skill named `entanglement` at its root.

## Manual installation and other harnesses

Clone the complete repository into your harness's skill directory. For example,
for project-local Claude Code:

```sh
mkdir -p .claude/skills
git clone https://github.com/alexandreteles/entanglement-skill .claude/skills/entanglement
```

Use an unused destination. Keep `scripts/` beside `SKILL.md` so the comparator
remains available.

| Harness | Project-local directory | User directory |
| --- | --- | --- |
| Claude Code | `.claude/skills/entanglement` | `~/.claude/skills/entanglement` |
| Codex | `.agents/skills/entanglement` | `~/.agents/skills/entanglement` |

Directory conventions are described in
[Claude Code's skills documentation](https://code.claude.com/docs/en/skills)
and the [official OpenAI documentation](https://learn.chatgpt.com/docs/build-skills).
For other harnesses, use their documented discovery directory. If a harness
has no skill discovery, clone anywhere and explicitly ask the agent to read
the absolute path to `SKILL.md` and follow it, with access to the sibling scripts.

## Use it during a coding task

Invoke the skill **before the agent edits source files**, so it can preserve
the starting baseline. Example in Codex:

```text
$entanglement Add input validation to the API, keep code growth justified,
and pass the file maintainability gate.
```

In Claude Code, use its slash-command form:

```text
/entanglement Add input validation to the API, keep code growth justified,
and pass the file maintainability gate.
```

For a harness without native invocation:

```text
Read /absolute/path/to/entanglement-skill/SKILL.md and follow it while adding
input validation to the API. Use the scripts beside that file.
```

The agent keeps a fixed baseline, analyzes the working tree after meaningful
edit batches, and reports NLOC, cyclomatic complexity, cognitive complexity,
and maintainability changes. Necessary feature growth is reviewed and explained.
Every added or modified supported task file must have unrounded file MI
**at least 10**; a red file must be split or reworked. Green (**20+**) is the
target, and yellow merits scrutiny. Unrelated existing red files are reported
as baseline debt. Ordinary syntax, build, and behavior checks remain part of
the task.

For a manual comparison, set `skill_dir` to the installed skill directory and
run from the project root:

```sh
skill_dir=/absolute/path/to/installed/entanglement
repo=$(pwd -P)
metrics_dir=$(mktemp -d)
entanglement repo "$repo" --metrics nloc,cc,cogc,mi --format json > "$metrics_dir/baseline.json"

# Make your code changes, then compare against the fixed baseline.
entanglement repo "$repo" --metrics nloc,cc,cogc,mi --format json > "$metrics_dir/after.json"
python3 "$skill_dir/scripts/compare.py" "$metrics_dir/baseline.json" "$metrics_dir/after.json" \
  --before-root "$repo" --after-root "$repo"
```

Check each command's exit status. The comparator prints a compact JSON summary:

| Exit | Meaning |
| --- | --- |
| `0` | No added or modified measured file is red; review growth separately. |
| `1` | An added or modified file is red; rework it and rerun. |
| `2` | Reports are missing, invalid, or incomplete; repair the analysis. |

Run the comparator explicitly to enforce the gate in CI or another automation.
Installing the skill provides instructions and scripts; hook configuration is
managed by your harness or project.

Use `candidate` to evaluate unapplied proposals against preserved before-state
source files. Reapplying a forward diff to an already edited tree can silently
duplicate additions. Use fresh `repo` reports for changes already on disk;
`patch` is useful for local diagnostics. See [SKILL.md](SKILL.md) for the complete
workflow and inventory checks.

## Validation

The workflow was tested across 18 project roots, with candidate/fresh-analysis
comparisons, realistic forward tests, and an independent reviewer. Scope and
limitations are recorded in [docs/validation.md](docs/validation.md).

Run the comparator's behavioral tests from this repository:

```sh
python3 -B -m unittest discover -s tests -v
```
