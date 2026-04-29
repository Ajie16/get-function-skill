#!/usr/bin/env python3
"""
Code Optimizer - Print Function String Extractor & Replacer
Extract string literal arguments from configured print functions,
optimize them in batches, and apply replacements back to source code.
"""

import argparse
import fnmatch
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


# Regex for C string literals: double-quoted with escape sequences
STRING_LITERAL_RE = re.compile(r'"(?:[^"\\]|\\.)*"')


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Any) -> None:
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(temp_path, path)


def offset_to_linecol(content: str, offset: int) -> tuple:
    """Convert character offset to (line, column), 1-based."""
    lines = content[:offset].split("\n")
    line = len(lines)
    col = len(lines[-1]) + 1 if lines else 1
    return line, col


def should_include_file(file_path: Path, patterns: List[str], exclude_patterns: List[str]) -> bool:
    name = file_path.name
    rel_path = str(file_path)
    matched = any(fnmatch.fnmatch(name, p) for p in patterns)
    if not matched:
        return False
    for ep in exclude_patterns:
        if "**" in ep:
            prefix = ep.split("/**")[0]
            if rel_path.startswith(prefix):
                return False
        elif fnmatch.fnmatch(name, ep) or fnmatch.fnmatch(rel_path, ep):
            return False
    return True


def is_binary_file(file_path: Path) -> bool:
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(8192)
            if b"\x00" in chunk:
                return True
        return False
    except OSError:
        return True


def extract_print_calls(content: str, func_name: str) -> List[Dict[str, Any]]:
    """Extract print function calls and their first string literal argument."""
    results = []
    func_pattern = re.compile(rf"\b{re.escape(func_name)}\s*\(")

    for match in func_pattern.finditer(content):
        paren_start = match.end() - 1

        # Find matching closing paren
        paren_depth = 1
        i = paren_start + 1
        while i < len(content) and paren_depth > 0:
            if content[i] == "(":
                paren_depth += 1
            elif content[i] == ")":
                paren_depth -= 1
            i += 1
        call_end = i

        # Search first string literal in arguments
        args_content = content[paren_start + 1 : call_end - 1]
        str_match = STRING_LITERAL_RE.search(args_content)

        if not str_match:
            continue

        str_abs_start = paren_start + 1 + str_match.start()
        str_abs_end = paren_start + 1 + str_match.end()

        call_code = content[match.start():call_end]
        line_start, col_start = offset_to_linecol(content, match.start())
        line_end, col_end = offset_to_linecol(content, call_end - 1)

        # Context: 3 lines before and after
        lines = content.splitlines()
        context_start = max(0, line_start - 4)
        context_end = min(len(lines), line_end + 3)

        results.append(
            {
                "lineStart": line_start,
                "lineEnd": line_end,
                "columnStart": col_start,
                "columnEnd": col_end,
                "code": call_code,
                "stringLiteral": str_match.group(0),
                "stringLiteralOffsetStart": str_abs_start,
                "stringLiteralOffsetEnd": str_abs_end,
                "context": "\n".join(lines[context_start:context_end]),
            }
        )

    return results


def resolve_git_repo(path_entry: Dict[str, Any]) -> str:
    git_repo = path_entry.get("gitRepo")
    if git_repo:
        return str(Path(git_repo).resolve())
    analysis_path = Path(path_entry["path"]).resolve()
    check_dir = analysis_path if analysis_path.is_dir() else analysis_path.parent
    for parent in [check_dir, *check_dir.parents]:
        if (parent / ".git").exists():
            return str(parent)
    return ""


def parse_path_entry(entry: Any) -> Dict[str, Any]:
    if isinstance(entry, str):
        return {"path": entry, "gitRepo": resolve_git_repo({"path": entry})}
    if isinstance(entry, dict):
        return {"path": entry.get("path", ""), "gitRepo": resolve_git_repo(entry)}
    return {"path": "", "gitRepo": ""}


def cmd_analyze(args: argparse.Namespace) -> None:
    config = load_json(args.config)
    paths_data = load_json(args.paths)

    target_functions = config.get("targetFunctions", [])
    file_patterns = config.get("filePatterns", ["*"])
    exclude_patterns = config.get("excludePatterns", [])
    raw_paths = paths_data.get("paths", [])

    if not target_functions:
        print("Error: targetFunctions not specified in config.json", file=sys.stderr)
        sys.exit(1)
    if not raw_paths:
        print("Error: paths not specified in paths.json", file=sys.stderr)
        sys.exit(1)

    path_entries = [parse_path_entry(p) for p in raw_paths]
    items: List[Dict[str, Any]] = []
    counter = 1
    cwd = Path.cwd()

    for entry in path_entries:
        path_str = entry["path"]
        git_repo = entry["gitRepo"]
        base_path = Path(path_str).resolve()

        if not base_path.exists():
            print(f"Warning: path does not exist, skipping: {base_path}", file=sys.stderr)
            continue

        all_files = [base_path] if base_path.is_file() else list(base_path.rglob("*"))

        for file_path in all_files:
            if not file_path.is_file():
                continue
            if not should_include_file(file_path, file_patterns, exclude_patterns):
                continue
            if is_binary_file(file_path):
                continue
            try:
                if file_path.stat().st_size > 1024 * 1024:
                    print(f"Warning: file too large, skipping: {file_path}", file=sys.stderr)
                    continue
            except OSError:
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            try:
                rel_path = str(file_path.relative_to(cwd))
            except ValueError:
                rel_path = str(file_path)

            for func_name in target_functions:
                calls = extract_print_calls(content, func_name)
                for call in calls:
                    items.append(
                        {
                            "id": f"call-{counter:03d}",
                            "functionName": func_name,
                            "filePath": rel_path,
                            "gitRepo": git_repo,
                            **call,
                            "status": "pending",
                            "batchId": None,
                            "optimizedAt": None,
                            "notes": "",
                        }
                    )
                    counter += 1

    result = {
        "version": "1.0",
        "generatedAt": datetime.now().isoformat(),
        "stats": {
            "total": len(items),
            "pending": len(items),
            "completed": 0,
        },
        "items": items,
    }

    save_json(args.output, result)
    print(f"Analysis complete. Extracted {len(items)} string literals. Saved to {args.output}")


def cmd_get(args: argparse.Namespace) -> None:
    data = load_json(args.input)
    items = data.get("items", [])
    batch_size = args.batch

    pending_items = [item for item in items if item.get("status") == "pending"]

    if not pending_items:
        print("All functions optimized.")
        return

    batch_id = f"batch-{int(datetime.now().timestamp())}"

    if args.group_by_file:
        # Group pending items by filePath, take first batch_size files
        from collections import OrderedDict
        files_map: OrderedDict[str, list] = OrderedDict()
        for item in pending_items:
            fp = item.get("filePath", "")
            if fp not in files_map:
                files_map[fp] = []
            files_map[fp].append(item)

        selected_files = list(files_map.keys())[:batch_size]
        to_process = []
        for fp in selected_files:
            to_process.extend(files_map[fp])
    else:
        to_process = pending_items[:batch_size]

    for item in to_process:
        item["batchId"] = batch_id

    save_json(args.input, data)

    def _make_output_item(item: dict) -> dict:
        if args.format == "minimal":
            return {
                "id": item["id"],
                "stringLiteral": item["stringLiteral"],
            }
        return item

    output_items = [_make_output_item(item) for item in to_process]

    output: dict = {
        "batchId": batch_id,
        "count": len(to_process),
        "remaining": len(pending_items) - len(to_process),
        "items": output_items,
    }

    if args.group_by_file:
        from collections import OrderedDict
        grouped: OrderedDict[str, list] = OrderedDict()
        for item in output_items:
            fp = item.get("filePath", "")
            if fp not in grouped:
                grouped[fp] = []
            grouped[fp].append(item)
        output["groupedByFile"] = dict(grouped)

    print(json.dumps(output, ensure_ascii=False, indent=2))


def cmd_mark_done(args: argparse.Namespace) -> None:
    if not args.ids and not args.batch_id:
        print("Error: must specify --ids or --batch-id", file=sys.stderr)
        sys.exit(1)
    if args.ids and args.batch_id:
        print("Error: --ids and --batch-id cannot be used together", file=sys.stderr)
        sys.exit(1)

    data = load_json(args.input)
    items = data.get("items", [])

    if args.batch_id:
        target_items = [
            item for item in items
            if item.get("batchId") == args.batch_id and item.get("status") == "pending"
        ]
        ids_to_mark = {item["id"] for item in target_items}
        if not ids_to_mark:
            print(f"Warning: no pending items for batch-id '{args.batch_id}'", file=sys.stderr)
    else:
        ids_to_mark = set(args.ids.split(","))

    marked_count = 0
    for item in items:
        item_id = item.get("id")
        if item_id not in ids_to_mark:
            continue
        if item.get("status") != "pending":
            continue
        item["status"] = "completed"
        item["optimizedAt"] = datetime.now().isoformat()
        marked_count += 1

    found_ids = {item.get("id") for item in items}
    skipped_not_found = list(ids_to_mark - found_ids)

    completed = sum(1 for item in items if item.get("status") == "completed")
    pending = sum(1 for item in items if item.get("status") == "pending")
    data["stats"] = {"total": len(items), "pending": pending, "completed": completed}

    save_json(args.input, data)
    print(f"Marked {marked_count}/{len(ids_to_mark)} items as completed")
    if skipped_not_found:
        print(f"  Skipped (ID not found): {', '.join(skipped_not_found)}")


def cmd_status(args: argparse.Namespace) -> None:
    data = load_json(args.input)
    stats = data.get("stats", {})
    total = stats.get("total", 0)
    pending = stats.get("pending", 0)
    completed = stats.get("completed", 0)

    if total == 0:
        print("No data")
        if args.strict:
            sys.exit(1)
        return

    percentage = (completed / total * 100) if total > 0 else 0
    print(f"Progress: {completed}/{total} ({percentage:.1f}%)")
    print(f"  - Pending: {pending}")
    print(f"  - Completed: {completed}")

    if pending == 0:
        print("\nAll optimizations complete")
    elif args.strict:
        sys.exit(1)


def cmd_apply(args: argparse.Namespace) -> None:
    """Apply replacements from replacements.json back to source files."""
    data = load_json(args.input)
    replacements_data = load_json(args.replacements)
    items = data.get("items", [])
    replacements = replacements_data.get("replacements", [])

    if not replacements:
        print("No replacements found.")
        return

    # Build replacement map by id
    replacement_map = {r["id"]: r["replacement"] for r in replacements if "id" in r and "replacement" in r}

    # Group items by filePath
    file_replacements: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        item_id = item.get("id")
        if item_id not in replacement_map:
            continue
        file_path = item.get("filePath")
        if file_path not in file_replacements:
            file_replacements[file_path] = []
        file_replacements[file_path].append(item)

    applied_count = 0

    for file_path, file_items in file_replacements.items():
        abs_path = Path(file_path).resolve()
        if not abs_path.exists():
            print(f"Warning: file not found: {file_path}", file=sys.stderr)
            continue

        try:
            content = abs_path.read_text(encoding="utf-8")
        except OSError as e:
            print(f"Warning: cannot read file {file_path}: {e}", file=sys.stderr)
            continue

        # Sort by offset in descending order to avoid offset shifts
        file_items.sort(key=lambda x: x.get("stringLiteralOffsetStart", 0), reverse=True)

        modified = False
        for item in file_items:
            item_id = item.get("id")
            start = item.get("stringLiteralOffsetStart")
            end = item.get("stringLiteralOffsetEnd")
            original = item.get("stringLiteral")
            replacement = replacement_map.get(item_id)

            if start is None or end is None or replacement is None:
                continue

            # Verify the original string is still at that position
            if content[start:end] != original:
                print(f"Warning: original string mismatch for {item_id} in {file_path}, skipping", file=sys.stderr)
                continue

            content = content[:start] + replacement + content[end:]
            modified = True

            # Update item status
            item["status"] = "completed"
            item["optimizedAt"] = datetime.now().isoformat()
            item["notes"] = f"Replaced with: {replacement}"
            applied_count += 1

        if modified:
            # Atomic write
            temp_path = str(abs_path) + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(temp_path, str(abs_path))
            print(f"Applied replacements to {file_path}")

    # Update stats
    completed = sum(1 for item in items if item.get("status") == "completed")
    pending = sum(1 for item in items if item.get("status") == "pending")
    data["stats"] = {"total": len(items), "pending": pending, "completed": completed}

    save_json(args.input, data)
    print(f"Applied {applied_count} replacements.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Code Optimizer - Print string extraction and replacement"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="Extract print function string literals")
    analyze_parser.add_argument("--config", required=True, help="Config JSON path")
    analyze_parser.add_argument("--paths", required=True, help="Paths JSON path")
    analyze_parser.add_argument("--output", required=True, help="Output extracted JSON path")

    # get
    get_parser = subparsers.add_parser("get", help="Get a batch of pending items")
    get_parser.add_argument("--input", required=True, help="Extracted JSON path")
    get_parser.add_argument("--batch", type=int, default=30, help="Batch size (default 30)")
    get_parser.add_argument(
        "--format",
        choices=["full", "minimal"],
        default="minimal",
        help="Output format: minimal (id+stringLiteral only, default, saves tokens) or full (all fields)",
    )
    get_parser.add_argument(
        "--group-by-file",
        action="store_true",
        help="Group items by filePath. --batch controls number of files (not items). "
             "Useful for large codebases to keep AI focused on one file at a time.",
    )

    # mark-done
    mark_parser = subparsers.add_parser("mark-done", help="Mark items as completed")
    mark_parser.add_argument("--input", required=True, help="Extracted JSON path")
    mark_parser.add_argument("--ids", help="Comma-separated IDs")
    mark_parser.add_argument("--batch-id", help="Batch ID to mark all as done")

    # status
    status_parser = subparsers.add_parser("status", help="Show progress")
    status_parser.add_argument("--input", required=True, help="Extracted JSON path")
    status_parser.add_argument("--strict", action="store_true", help="Exit with non-zero if incomplete")

    # apply
    apply_parser = subparsers.add_parser("apply", help="Apply replacements to source files")
    apply_parser.add_argument("--input", required=True, help="Extracted JSON path")
    apply_parser.add_argument("--replacements", required=True, help="Replacements JSON path")

    args = parser.parse_args()

    if args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "get":
        cmd_get(args)
    elif args.command == "mark-done":
        cmd_mark_done(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "apply":
        cmd_apply(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
