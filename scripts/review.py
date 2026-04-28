#!/usr/bin/env python3
"""
Review Tool for code-optimizer.

Generates a self-contained static HTML page for human review of AI-generated
replacements. Supports inline editing, skip toggling, and export to
replacements.json.

Usage:
    python review.py --input extracted.json [--replacements replacements.json] --output review.html

The output HTML is fully self-contained (no server needed). Open it in a
browser, edit replacements, toggle skip, then click "Download" to save
the updated replacements.json. Run replacements.py apply separately to
apply changes to source files.
"""

import argparse
import html
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def escape_js_string(s: str) -> str:
    """Escape a string for safe embedding in JS."""
    return json.dumps(s)


def generate_review_html(extracted: dict, replacements: list, title: str = "Code Optimizer Review") -> str:
    items = extracted.get("items", [])
    stats = extracted.get("stats", {})
    replacement_map = {r["id"]: r["replacement"] for r in replacements if "id" in r}

    # Build review items: merge extracted + replacement data
    review_items = []
    for item in items:
        if item.get("status") != "pending":
            continue
        item_id = item.get("id", "")
        review_items.append({
            "id": item_id,
            "filePath": item.get("filePath", ""),
            "lineStart": item.get("lineStart", 0),
            "code": item.get("code", ""),
            "stringLiteral": item.get("stringLiteral", ""),
            "context": item.get("context", ""),
            "replacement": replacement_map.get(item_id, ""),
        })

    extracted_json = escape_js_string(json.dumps(extracted, ensure_ascii=False))
    replacements_json = escape_js_string(json.dumps(replacements, ensure_ascii=False))
    review_items_json = escape_js_string(json.dumps(review_items, ensure_ascii=False))

    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
<style>
:root {{
  --bg: #0d1117;
  --surface: #161b22;
  --surface-hover: #1f242c;
  --border: #30363d;
  --text: #c9d1d9;
  --text-dim: #8b949e;
  --accent: #58a6ff;
  --accent-hover: #79b8ff;
  --success: #3fb950;
  --warning: #d29922;
  --danger: #f85149;
  --font-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: var(--font-sans);
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
  min-height: 100vh;
}}
.container {{ max-width: 1400px; margin: 0 auto; padding: 24px; }}
header {{ margin-bottom: 24px; }}
header h1 {{ font-size: 24px; font-weight: 600; margin-bottom: 8px; }}
header p {{ color: var(--text-dim); font-size: 14px; }}

.stats {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}}
.stat-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
  text-align: center;
}}
.stat-card .value {{
  font-size: 28px;
  font-weight: 700;
  color: var(--accent);
}}
.stat-card .label {{
  font-size: 12px;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-top: 4px;
}}

.toolbar {{
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  margin-bottom: 16px;
  padding: 12px 16px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
}}
.toolbar input[type="text"] {{
  flex: 1;
  min-width: 200px;
  padding: 8px 12px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  font-size: 14px;
}}
.toolbar input[type="text"]::placeholder {{ color: var(--text-dim); }}
.toolbar button {{
  padding: 8px 16px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface-hover);
  color: var(--text);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}}
.toolbar button:hover {{ background: var(--border); }}
.toolbar button.primary {{
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}}
.toolbar button.primary:hover {{ background: var(--accent-hover); }}
.toolbar button.danger {{ color: var(--danger); border-color: var(--danger); }}
.toolbar button.danger:hover {{ background: rgba(248,81,73,0.1); }}

.table-wrap {{
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
}}
table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}}
thead th {{
  position: sticky;
  top: 0;
  background: var(--surface-hover);
  padding: 10px 12px;
  text-align: left;
  font-weight: 600;
  color: var(--text-dim);
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}}
tbody tr {{ border-bottom: 1px solid var(--border); transition: background 0.1s; }}
tbody tr:hover {{ background: var(--surface-hover); }}
tbody tr.skipped {{ opacity: 0.4; }}
tbody td {{ padding: 10px 12px; vertical-align: top; }}
tbody td:first-child {{ text-align: center; }}

td .file-line {{
  color: var(--text-dim);
  font-size: 12px;
  font-family: var(--font-mono);
  cursor: pointer;
  user-select: none;
  display: flex;
  align-items: center;
  gap: 6px;
}}
td .file-line::before {{
  content: '▸';
  display: inline-block;
  transition: transform 0.2s;
  color: var(--accent);
}}
td .file-line.expanded::before {{
  transform: rotate(90deg);
}}
td .code {{
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-dim);
  margin-top: 4px;
  padding: 6px 8px;
  background: var(--bg);
  border-radius: 4px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  display: none;
}}
td .code.expanded {{
  display: block;
  animation: fadeIn 0.2s ease;
}}
td .code-path {{
  font-size: 11px;
  color: var(--text-dim);
  margin-bottom: 4px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--border);
}}
@keyframes fadeIn {{
  from {{ opacity: 0; transform: translateY(-4px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}
td .literal {{
  font-family: var(--font-mono);
  font-size: 14px;
  color: #a5d6ff;
  word-break: break-all;
  font-weight: 500;
  background: rgba(88,166,255,0.06);
  border: 1px solid rgba(88,166,255,0.15);
  border-radius: 4px;
  padding: 8px;
  display: block;
  line-height: 1.5;
}}
td textarea.edit {{
  width: 100%;
  min-height: 64px;
  padding: 8px 10px;
  background: rgba(88,166,255,0.04);
  border: 1px solid rgba(88,166,255,0.25);
  border-radius: 4px;
  color: #a5d6ff;
  font-family: var(--font-mono);
  font-size: 14px;
  line-height: 1.5;
  resize: vertical;
}}
td textarea.edit:focus {{
  outline: none;
  border-color: var(--accent);
  background: rgba(88,166,255,0.08);
}}
.str-row {{
  margin-bottom: 8px;
}}
.str-row:last-child {{
  margin-bottom: 0;
}}
.str-label {{
  font-size: 11px;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
  font-weight: 600;
}}
td .status-badge {{
  display: inline-block;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
}}
td .status-badge.has-replacement {{ background: rgba(88,166,255,0.15); color: var(--accent); }}
td .status-badge.no-replacement {{ background: rgba(139,148,158,0.15); color: var(--text-dim); }}
td .status-badge.skipped {{ background: rgba(248,81,73,0.15); color: var(--danger); }}

input[type="checkbox"] {{
  width: 16px;
  height: 16px;
  accent-color: var(--accent);
  cursor: pointer;
}}

.empty-state {{
  text-align: center;
  padding: 60px 20px;
  color: var(--text-dim);
}}
.empty-state h2 {{ font-size: 18px; margin-bottom: 8px; color: var(--text); }}

.export-panel {{
  position: fixed;
  bottom: 20px;
  right: 20px;
  display: flex;
  gap: 10px;
}}
.export-panel button {{
  padding: 12px 24px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  transition: transform 0.15s;
}}
.export-panel button:hover {{ transform: translateY(-2px); }}
.export-panel .btn-export {{
  background: var(--success);
  color: #fff;
}}
.export-panel .btn-export:disabled {{
  background: var(--text-dim);
  cursor: not-allowed;
  transform: none;
}}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>🔍 {html.escape(title)}</h1>
    <p>Review AI-generated replacements before applying. Edit inline, toggle skip, then save or export.</p>
  </header>

  <div class="stats" id="stats"></div>

  <div class="toolbar">
    <input type="text" id="search" placeholder="Search by file, ID, or string content...">
    <button onclick="selectAll(true)">Select All</button>
    <button onclick="selectAll(false)">Deselect All</button>
    <button class="danger" onclick="skipAllNoReplacement()">Skip Empty</button>
    <button class="primary" onclick="saveToFile()">💾 Save</button>
    <button class="primary" onclick="copyToClipboard()">📋 Copy JSON</button>
    <button onclick="exportReplacements()">⬇ Download</button>
    <button class="primary" style="background:var(--success);border-color:var(--success);" onclick="applyChanges()" id="btn-apply">🚀 Apply</button>
  </div>

  <div id="apply-panel" style="display:none;margin-bottom:16px;padding:16px;background:var(--surface);border:1px solid var(--border);border-radius:8px;">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
      <span id="apply-status-icon"></span>
      <strong id="apply-status-text" style="font-size:14px;"></strong>
    </div>
    <pre id="apply-stdout" style="font-family:var(--font-mono);font-size:12px;background:var(--bg);padding:10px;border-radius:4px;overflow-x:auto;max-height:200px;overflow-y:auto;margin-bottom:8px;display:none;"></pre>
    <pre id="apply-stderr" style="font-family:var(--font-mono);font-size:12px;color:var(--danger);background:rgba(248,81,73,0.05);padding:10px;border-radius:4px;overflow-x:auto;max-height:200px;overflow-y:auto;display:none;"></pre>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th style="width:40px"><input type="checkbox" id="check-all" onchange="toggleAll(this.checked)"></th>
          <th>ID</th>
          <th>Location</th>
          <th>String Comparison</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
    <div id="empty" class="empty-state" style="display:none">
      <h2>No pending items</h2>
      <p>All optimizations are complete, or nothing matches your search.</p>
    </div>
  </div>
</div>

<script>
const EXTRACTED = JSON.parse({extracted_json});
const INITIAL_REPLACEMENTS = JSON.parse({replacements_json});
const REVIEW_ITEMS = JSON.parse({review_items_json});

// State: id -> {{ replacement, skipped }}
let state = {{}};
let filterText = '';

function saveStateToLocal() {{
  try {{
    localStorage.setItem('review_state_v1', JSON.stringify(state));
  }} catch (e) {{}}
}}

function loadStateFromLocal() {{
  try {{
    const saved = localStorage.getItem('review_state_v1');
    return saved ? JSON.parse(saved) : null;
  }} catch (e) {{
    return null;
  }}
}}

function clearStateLocal() {{
  try {{
    localStorage.removeItem('review_state_v1');
  }} catch (e) {{}}
}}

async function initState() {{
  // 1. Build base state from embedded data
  REVIEW_ITEMS.forEach(item => {{
    state[item.id] = {{
      replacement: item.replacement,
      skipped: false
    }};
  }});

  // 2. Overlay local edits from previous session
  const localState = loadStateFromLocal();
  if (localState) {{
    Object.keys(localState).forEach(id => {{
      if (state[id]) {{
        state[id].replacement = localState[id].replacement;
        state[id].skipped = localState[id].skipped;
      }}
    }});
  }}

  render();
}}

function render() {{
  const tbody = document.getElementById('tbody');
  const empty = document.getElementById('empty');
  const filtered = REVIEW_ITEMS.filter(item => {{
    const s = filterText.toLowerCase();
    return !s ||
      item.id.toLowerCase().includes(s) ||
      item.filePath.toLowerCase().includes(s) ||
      item.stringLiteral.toLowerCase().includes(s) ||
      (state[item.id].replacement || '').toLowerCase().includes(s);
  }});

  if (filtered.length === 0) {{
    tbody.innerHTML = '';
    empty.style.display = '';
    updateStats(0, 0, 0);
    return;
  }}
  empty.style.display = 'none';

  let html = '';
  let selectedCount = 0;
  let skippedCount = 0;
  let withReplacement = 0;

  filtered.forEach(item => {{
    const st = state[item.id];
    const isSkipped = st.skipped;
    const hasRep = !!st.replacement;
    if (!isSkipped) selectedCount++;
    if (isSkipped) skippedCount++;
    if (hasRep) withReplacement++;

    const rowClass = isSkipped ? 'skipped' : '';
    const statusClass = isSkipped ? 'skipped' : (hasRep ? 'has-replacement' : 'no-replacement');
    const statusText = isSkipped ? 'Skipped' : (hasRep ? 'Ready' : 'Empty');

    html += `<tr class="${{rowClass}}" data-id="${{item.id}}">
      <td><input type="checkbox" ${{isSkipped ? '' : 'checked'}}
        onchange="toggleItem('${{item.id}}', this.checked)"></td>
      <td>${{esc(item.id)}}</td>
      <td>
        <div class="file-line" onclick="toggleCode('${{item.id}}')">${{esc(item.filePath.split('/').pop())}}:${{item.lineStart}}</div>
        <div class="code" id="code-${{item.id}}"><div class="code-path">${{esc(item.filePath)}}</div>${{esc(item.code)}}</div>
      </td>
      <td>
        <div class="str-row">
          <div class="str-label">Original</div>
          <span class="literal">${{esc(item.stringLiteral)}}</span>
        </div>
        <div class="str-row">
          <div class="str-label">AI</div>
          <textarea class="edit"
            oninput="updateReplacement('${{item.id}}', this.value)"
            placeholder='Type replacement string with quotes...'>${{esc(st.replacement)}}</textarea>
        </div>
      </td>
      <td><span class="status-badge ${{statusClass}}">${{statusText}}</span></td>
    </tr>`;
  }});

  tbody.innerHTML = html;
  updateStats(filtered.length, selectedCount, skippedCount);

  // Update master checkbox
  const allChecked = filtered.length > 0 && filtered.every(i => !state[i.id].skipped);
  const someChecked = filtered.some(i => !state[i.id].skipped);
  const master = document.getElementById('check-all');
  master.checked = allChecked;
  master.indeterminate = someChecked && !allChecked;
}}

function updateStats(total, selected, skipped) {{
  const withRep = REVIEW_ITEMS.filter(i => !!state[i.id].replacement).length;
  document.getElementById('stats').innerHTML = `
    <div class="stat-card"><div class="value">${{total}}</div><div class="label">Visible</div></div>
    <div class="stat-card"><div class="value">${{selected}}</div><div class="label">Selected</div></div>
    <div class="stat-card"><div class="value">${{skipped}}</div><div class="label">Skipped</div></div>
    <div class="stat-card"><div class="value">${{withRep}}</div><div class="label">With Replacement</div></div>
  `;
}}

function esc(s) {{
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}}

function toggleCode(id) {{
  const codeEl = document.getElementById('code-' + id);
  const fileLineEl = codeEl.previousElementSibling;
  if (codeEl.classList.contains('expanded')) {{
    codeEl.classList.remove('expanded');
    fileLineEl.classList.remove('expanded');
  }} else {{
    codeEl.classList.add('expanded');
    fileLineEl.classList.add('expanded');
  }}
}}

function toggleItem(id, checked) {{
  state[id].skipped = !checked;
  saveStateToLocal();
  render();
}}

function toggleAll(checked) {{
  const visible = getVisibleIds();
  visible.forEach(id => {{ state[id].skipped = !checked; }});
  saveStateToLocal();
  render();
}}

function selectAll(checked) {{
  Object.keys(state).forEach(id => {{ state[id].skipped = !checked; }});
  saveStateToLocal();
  render();
}}

function skipAllNoReplacement() {{
  Object.keys(state).forEach(id => {{
    if (!state[id].replacement) state[id].skipped = true;
  }});
  saveStateToLocal();
  render();
}}

function getVisibleIds() {{
  const s = filterText.toLowerCase();
  return REVIEW_ITEMS
    .filter(i => !s ||
      i.id.toLowerCase().includes(s) ||
      i.filePath.toLowerCase().includes(s) ||
      i.stringLiteral.toLowerCase().includes(s) ||
      (state[i.id].replacement || '').toLowerCase().includes(s))
    .map(i => i.id);
}}

let autoSaveTimer = null;

function updateReplacement(id, value) {{
  state[id].replacement = value;
  // Auto-unskip if user types something
  if (value && state[id].skipped) {{
    state[id].skipped = false;
    render();
  }}
  // Persist to localStorage so edits survive page refresh
  saveStateToLocal();
  // Auto-save after 1s of inactivity
  clearTimeout(autoSaveTimer);
  showAutoSaveStatus('Saving...');
  autoSaveTimer = setTimeout(() => {{
    autoSaveToFile();
  }}, 1000);
}}

function autoSaveToFile() {{
  // Edits are persisted to localStorage automatically.
  // Use Download or Copy JSON to export replacements.json.
  showAutoSaveStatus('Saved locally');
  setTimeout(() => {{ showAutoSaveStatus(''); }}, 2000);
}}

function showAutoSaveStatus(text) {{
  let el = document.getElementById('autosave-status');
  if (!el) {{
    el = document.createElement('div');
    el.id = 'autosave-status';
    el.style.cssText = 'position:fixed;bottom:20px;left:20px;padding:6px 12px;background:var(--surface);border:1px solid var(--border);border-radius:6px;font-size:12px;color:var(--text-dim);z-index:1000;transition:opacity 0.3s;';
    document.body.appendChild(el);
  }}
  el.textContent = text;
  el.style.opacity = '1';
  if (text === 'Saved') {{
    setTimeout(() => {{ el.style.opacity = '0'; }}, 2000);
  }}
}}

document.getElementById('search').addEventListener('input', e => {{
  filterText = e.target.value;
  render();
}});

function getExportData() {{
  const reps = [];
  REVIEW_ITEMS.forEach(item => {{
    const st = state[item.id];
    if (st.skipped || !st.replacement) return;
    reps.push({{ id: item.id, replacement: st.replacement }});
  }});
  return {{ version: "1.0", generatedAt: new Date().toISOString(), replacements: reps }};
}}

function getExportJson() {{
  return JSON.stringify(getExportData(), null, 2);
}}

function saveToFile() {{
  // In static mode, Save downloads the replacements.json file
  fallbackDownload(getExportJson());
  clearStateLocal();
}}

async function copyToClipboard() {{
  const json = getExportJson();
  try {{
    await navigator.clipboard.writeText(json);
    showBtnFeedback('.btn-copy', '✓ Copied to clipboard');
  }} catch (err) {{
    console.error(err);
    alert('Copy failed. Please use Download instead.');
  }}
}}

function fallbackDownload(json) {{
  const blob = new Blob([json], {{ type: 'application/json' }});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'replacements.json';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showBtnFeedback('.btn-export', `✓ Downloaded ${{getExportData().replacements.length}} replacements`);
}}

function exportReplacements() {{
  fallbackDownload(getExportJson());
}}

function showBtnFeedback(selector, text) {{
  const btn = document.querySelector(selector);
  if (!btn) return;
  const orig = btn.textContent;
  btn.textContent = text;
  btn.disabled = true;
  setTimeout(() => {{ btn.textContent = orig; btn.disabled = false; }}, 2000);
}}

function applyChanges() {{
  const panel = document.getElementById('apply-panel');
  const statusIcon = document.getElementById('apply-status-icon');
  const statusText = document.getElementById('apply-status-text');
  const stdoutEl = document.getElementById('apply-stdout');
  const stderrEl = document.getElementById('apply-stderr');

  panel.style.display = 'block';
  statusIcon.textContent = '💡';
  statusText.textContent = 'Manual apply required';
  stdoutEl.style.display = 'none';

  const reps = [];
  REVIEW_ITEMS.forEach(item => {{
    const st = state[item.id];
    if (st.skipped || !st.replacement) return;
    reps.push({{ id: item.id, replacement: st.replacement }});
  }});

  if (reps.length === 0) {{
    stderrEl.textContent = 'No replacements to apply. Edit some strings first.';
    stderrEl.style.color = 'var(--danger)';
    stderrEl.style.display = 'block';
    return;
  }}

  stderrEl.textContent = 'Step 1: Click "Download" to save replacements.json\n' +
    'Step 2: Run in terminal:\n' +
    '  python skills/code-optimizer/scripts/replacements.py apply --input extracted.json\n\n' +
    'Ready to apply: ' + reps.length + ' replacements';
  stderrEl.style.color = 'var(--text)';
  stderrEl.style.display = 'block';
}}

initState();
</script>
</body>
</html>'''
    return html_content



def main() -> None:
    parser = argparse.ArgumentParser(description="Generate review HTML for code-optimizer replacements")
    parser.add_argument("--input", required=True, help="Extracted JSON path")
    parser.add_argument("--replacements", default="replacements.json", help="Replacements JSON path (default: replacements.json)")
    parser.add_argument("--output", required=True, help="Output HTML path")
    parser.add_argument("--title", default="Code Optimizer Review", help="Page title")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: extracted file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    extracted = load_json(args.input)
    replacements = []
    if os.path.exists(args.replacements):
        replacements = load_json(args.replacements).get("replacements", [])

    html_content = generate_review_html(extracted, replacements, args.title)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html_content)

    pending_count = sum(1 for item in extracted.get("items", []) if item.get("status") == "pending")
    print(f"Review page generated: {args.output}")
    print(f"  Pending items: {pending_count}")
    print(f"  Replacements loaded: {len(replacements)}")
    print(f"  Open in browser: file://{os.path.abspath(args.output)}")


if __name__ == "__main__":
    main()
