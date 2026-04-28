# Advanced Usage

## Handling Large Codebases (1000+ items)

When the codebase contains thousands of print calls, AI context limits become the bottleneck. Use these strategies:

### 1. Reduce token consumption with `--format minimal`

Only sends `id`, `stringLiteral`, `filePath`, and `lineStart` — omitting `code`, `context`, and offsets:

```bash
python scripts/codebase.py get \
  --input extracted.json --batch 50 --format minimal
```

### 2. Group by file with `--group-by-file`

Process one file at a time. `--batch` controls the number of **files** (not items), so all pending items from each selected file are returned together:

```bash
python scripts/codebase.py get \
  --input extracted.json --batch 5 --format minimal --group-by-file
```

The output includes a `groupedByFile` map for easy per-file processing.

### 3. Tune batch size

| Scale | Recommended flags |
|-------|-------------------|
| < 200 items | `--batch 30` (default) |
| 200–1000 items | `--batch 50 --format minimal` |
| 1000+ items | `--batch 10 --format minimal --group-by-file` |

With `--group-by-file`, a `--batch` of 5–10 files usually keeps the response under AI context limits while minimizing total iterations.

---

## CLI Reference

### `codebase.py`

| Command | Arguments | Purpose |
|---------|-----------|---------|
| `analyze` | `--config`, `--paths`, `--output` | Scan paths, extract print function string literals → `extracted.json` |
| `get` | `--input`, `--batch` (default 30), `--format` (`full`\|`minimal`), `--group-by-file` | Return pending items, assign `batchId` |
| `mark-done` | `--input`, `--ids` or `--batch-id` | Manually mark items as completed |
| `status` | `--input`, `--strict` | Show progress stats; `--strict` exits non-zero if incomplete |

### `replacements.py`

| Command | Arguments | Purpose |
|---------|-----------|---------|
| `import` | `--file <json>` | Import replacements from AI-generated JSON |
| `add` | `--id <id>`, `--replacement <str>` | Add a single replacement |
| `remove` | `--id <id>` | Remove a replacement |
| `clear` | — | Remove all replacements |
| `list` | — | List all recorded replacements |
| `apply` | `--input <extracted.json>`, `--replacements` (default `replacements.json`) | Apply replacements to source files, update `extracted.json`, auto-clear applied entries |

---

## Review Tool (`review.py`)

Generate a self-contained static HTML page for human review of AI-generated replacements before applying them to source code.

```bash
python scripts/review.py \
  --input extracted.json \
  --replacements replacements.json \
  --output review.html
```

Open `review.html` in any browser — no server required.

### Features

- **Side-by-side view**: original string vs AI replacement for every pending item
- **Inline editing**: click the AI replacement cell and modify directly
- **Skip toggle**: uncheck items to exclude them from the exported replacements.json
- **Search/filter**: filter by file path, ID, or string content
- **Bulk actions**: select/deselect all, skip empty replacements
- **Export**: one-click download of the curated `replacements.json`

### Workflow with Review

```bash
# After AI generates replacements and you import them:
python scripts/replacements.py import --file ai-batch.json

# Generate review page
python scripts/review.py \
  --input extracted.json --replacements replacements.json --output review.html

# Open review.html in browser, edit / skip as needed, click Export
# The exported replacements.json overwrites the old one

# Then apply the reviewed replacements
python scripts/replacements.py apply --input extracted.json
```

---

## Safety Notes

- `apply` verifies the original `stringLiteral` still exists at the recorded offset before replacing. If mismatch, it skips that item.
- Replacements within a single file are applied in **descending offset order** to prevent position shifts from affecting subsequent replacements.
- File writes are **atomic** (write to `.tmp` then `os.replace`).
- After successful apply, `replacements.json` is **auto-cleared** to prevent accidental duplicate application.
