#!/usr/bin/env python3
"""
Replacements Manager for code-optimizer.

Manages replacements.json (CRUD) and applies replacements back to source files.

Workflow:
  1. AI generates replacements → import them
  2. Review / edit replacements via add/remove/list
  3. Apply replacements to source files

Commands:
  import    Import replacements from AI-generated JSON file
  add       Add a single replacement
  remove    Remove a replacement by ID
  clear     Remove all replacements
  list      List all recorded replacements
  apply     Apply replacements to source files (updates extracted.json)
"""

import argparse
import json
import os
import sys
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_REPLACEMENTS_FILE = "replacements.json"


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def ensure_replacements_file(path: str = DEFAULT_REPLACEMENTS_FILE) -> Dict[str, Any]:
    if not os.path.exists(path):
        data = {"version": "1.0", "replacements": []}
        save_json(path, data)
        return data
    return load_json(path)


def cmd_import(args: argparse.Namespace) -> None:
    """Import replacements from an AI-generated JSON file.

    Supports two formats:
      - Object: {"id": "call-001", "replacement": "\"str\""}
      - Compact array: ["call-001", "\"str\""]  (matches get output format)
    """
    src = load_json(args.file)
    src_replacements = src.get("replacements", [])
    if not src_replacements:
        print("Source file contains no replacements.")
        return

    data = ensure_replacements_file(args.output)
    existing_map = {r["id"]: r for r in data["replacements"]}

    added = 0
    updated = 0
    for rep in src_replacements:
        # Support compact array format [id, replacement]
        if isinstance(rep, list) and len(rep) >= 2:
            rep_id = rep[0]
            replacement = rep[1]
        elif isinstance(rep, dict):
            rep_id = rep.get("id")
            replacement = rep.get("replacement")
        else:
            continue

        if not rep_id or replacement is None:
            continue
        if rep_id in existing_map:
            existing_map[rep_id]["replacement"] = replacement
            updated += 1
        else:
            data["replacements"].append({"id": rep_id, "replacement": replacement})
            existing_map[rep_id] = data["replacements"][-1]
            added += 1

    save_json(args.output, data)
    print(f"Imported {added} new, updated {updated} existing replacements into {args.output}")


def cmd_add(args: argparse.Namespace) -> None:
    """Add or update a single replacement."""
    data = ensure_replacements_file(args.output)
    for r in data["replacements"]:
        if r["id"] == args.id:
            r["replacement"] = args.replacement
            save_json(args.output, data)
            print(f"Updated replacement for {args.id}")
            return

    data["replacements"].append({"id": args.id, "replacement": args.replacement})
    save_json(args.output, data)
    print(f"Added replacement for {args.id}")


def cmd_remove(args: argparse.Namespace) -> None:
    """Remove a replacement by ID."""
    data = ensure_replacements_file(args.output)
    original_len = len(data["replacements"])
    data["replacements"] = [r for r in data["replacements"] if r["id"] != args.id]

    if len(data["replacements"]) == original_len:
        print(f"Replacement {args.id} not found in {args.output}")
        return

    save_json(args.output, data)
    print(f"Removed replacement for {args.id}")


def cmd_clear(args: argparse.Namespace) -> None:
    """Clear all replacements."""
    data = ensure_replacements_file(args.output)
    count = len(data["replacements"])
    data["replacements"] = []
    save_json(args.output, data)
    print(f"Cleared {count} replacements from {args.output}")


def cmd_list(args: argparse.Namespace) -> None:
    """List all recorded replacements."""
    data = ensure_replacements_file(args.output)
    replacements = data.get("replacements", [])

    if not replacements:
        print("No replacements recorded.")
        return

    print(f"Total replacements in {args.output}: {len(replacements)}")
    for r in replacements:
        print(f"  {r['id']}: {r['replacement']}")


def cmd_apply(args: argparse.Namespace) -> None:
    """Apply replacements to source files and update extracted.json."""
    extracted_path = args.input
    replacements_path = args.replacements

    if not os.path.exists(replacements_path):
        print(f"Error: replacements file not found: {replacements_path}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(extracted_path):
        print(f"Error: extracted file not found: {extracted_path}", file=sys.stderr)
        sys.exit(1)

    extracted_data = load_json(extracted_path)
    extracted_items = extracted_data.get("items", [])
    id_map = {item["id"]: item for item in extracted_items}

    replacements_data = load_json(replacements_path)
    replacements = replacements_data.get("replacements", [])

    if not replacements:
        print("No replacements to apply.")
        return

    # Group by filePath
    file_items_map: Dict[str, List[Any]] = {}
    for rep in replacements:
        item = id_map.get(rep["id"])
        if not item:
            print(f"SKIP {rep['id']}: not found in extracted.json")
            continue
        fp = item.get("filePath")
        if fp not in file_items_map:
            file_items_map[fp] = []
        file_items_map[fp].append(item)

    replacement_map = {r["id"]: r["replacement"] for r in replacements}
    applied_count = 0

    for file_path, file_items in file_items_map.items():
        abs_path = Path(file_path).resolve()
        if not abs_path.exists():
            # Try resolving relative to gitRepo if available
            git_repo = file_items[0].get("gitRepo") if file_items else None
            if git_repo:
                repo_path = Path(git_repo).resolve()
                candidate = (repo_path / file_path).resolve()
                if candidate.exists():
                    abs_path = candidate
                else:
                    print(f"Warning: file not found: {file_path} (tried {candidate})", file=sys.stderr)
                    continue
            else:
                print(f"Warning: file not found: {file_path}", file=sys.stderr)
                continue

        try:
            content = abs_path.read_text(encoding="utf-8")
        except OSError as e:
            print(f"Warning: cannot read file {file_path}: {e}", file=sys.stderr)
            continue

        # Sort by offset descending to avoid position shifts
        file_items.sort(key=lambda x: x.get("stringLiteralOffsetStart", 0), reverse=True)

        modified = False
        for item in file_items:
            item_id = item["id"]
            start = item.get("stringLiteralOffsetStart")
            end = item.get("stringLiteralOffsetEnd")
            original = item.get("stringLiteral")
            replacement = replacement_map.get(item_id)

            if start is None or end is None or replacement is None:
                continue

            if content[start:end] != original:
                print(f"Warning: original string mismatch for {item_id} in {file_path}, skipping", file=sys.stderr)
                continue

            content = content[:start] + replacement + content[end:]
            modified = True

            item["status"] = "completed"
            item["optimizedAt"] = datetime.now().isoformat()
            item["notes"] = f"Replaced with: {replacement}"
            applied_count += 1

        if modified:
            temp_path = str(abs_path) + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(temp_path, str(abs_path))
            print(f"Applied replacements to {file_path}")

    # Update stats
    completed = sum(1 for item in extracted_items if item.get("status") == "completed")
    pending = sum(1 for item in extracted_items if item.get("status") == "pending")
    extracted_data["stats"] = {"total": len(extracted_items), "pending": pending, "completed": completed}

    save_json(extracted_path, extracted_data)
    print(f"Applied {applied_count}/{len(replacements)} replacements.")

    # NOTE: replacements file is kept for audit/review purposes after apply


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replacements Manager for code-optimizer"
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_REPLACEMENTS_FILE,
        help=f"Replacements JSON path (default: {DEFAULT_REPLACEMENTS_FILE})",
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # import
    import_parser = subparsers.add_parser("import", help="Import from AI-generated JSON")
    import_parser.add_argument("--file", required=True, help="Source JSON path")

    # add
    add_parser = subparsers.add_parser("add", help="Add a replacement")
    add_parser.add_argument("--id", required=True, help="Item ID")
    add_parser.add_argument("--replacement", required=True, help="New string literal with quotes")

    # remove
    remove_parser = subparsers.add_parser("remove", help="Remove a replacement")
    remove_parser.add_argument("--id", required=True, help="Item ID")

    # clear
    subparsers.add_parser("clear", help="Remove all replacements")

    # list
    subparsers.add_parser("list", help="List all replacements")

    # apply
    apply_parser = subparsers.add_parser("apply", help="Apply replacements to source files")
    apply_parser.add_argument("--input", required=True, help="Extracted JSON path")
    apply_parser.add_argument(
        "--replacements",
        default=DEFAULT_REPLACEMENTS_FILE,
        help=f"Replacements JSON path (default: {DEFAULT_REPLACEMENTS_FILE})",
    )

    args = parser.parse_args()

    if args.command == "import":
        cmd_import(args)
    elif args.command == "add":
        cmd_add(args)
    elif args.command == "remove":
        cmd_remove(args)
    elif args.command == "clear":
        cmd_clear(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "apply":
        cmd_apply(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
