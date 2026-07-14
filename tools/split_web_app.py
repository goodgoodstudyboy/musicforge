from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


FUNCTION_START = re.compile(r"^    (?:(async) )?function ([A-Za-z_$][A-Za-z0-9_$]*)\(")
STATE_DECLARATION = re.compile(r"^    let ([A-Za-z_$][A-Za-z0-9_$]*) = (.*);$")


def split_web_app(path: Path, *, source: str | None = None, target_lines: int = 850) -> list[Path]:
    source = path.read_text(encoding="utf-8") if source is None else source
    lines = source.splitlines()
    scripts = path.parent
    for child in scripts.iterdir():
        if child.name == "app.js":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        elif child.suffix in {".js", ".json"}:
            child.unlink()
    panels = scripts / "panels"
    panels.mkdir()

    removed: set[int] = set()
    state_lines: list[str] = []
    function_rows: list[tuple[str, int, int, list[str]]] = []
    for index, line in enumerate(lines):
        state = STATE_DECLARATION.match(line)
        if state:
            state_lines.append(f"globalThis.{state.group(1)} = {state.group(2)};")
            removed.add(index)
            continue
        match = FUNCTION_START.match(line)
        if not match:
            continue
        end = _find_exact_line(lines, index + 1, "    }")
        chunk = [_dedent(item) for item in lines[index : end + 1]]
        function_rows.append((match.group(2), index, end, chunk))
        removed.update(range(index, end + 1))

    arrow_rows: list[tuple[str, int, int, list[str]]] = []
    for index, line in enumerate(lines):
        if index in removed or not line.startswith("    const "):
            continue
        name = line.strip().split()[1]
        end = index if line.rstrip().endswith(";") else _find_exact_line(lines, index + 1, "    };")
        chunk = [_dedent(item) for item in lines[index : end + 1]]
        chunk[0] = chunk[0].replace(f"const {name} =", f"globalThis.{name} =", 1)
        arrow_rows.append((name, index, end, chunk))
        removed.update(range(index, end + 1))

    state = "\n".join(
        [
            "globalThis.MusicForgePanels = Object.create(null);",
            *state_lines,
            "export const panels = globalThis.MusicForgePanels;",
        ]
    ) + "\n"
    outputs = [_write(scripts / "state.js", state)]

    categorized: dict[str, list[tuple[str, list[str]]]] = {}
    for name, _start, _end, chunk in function_rows:
        categorized.setdefault(_category(name), []).append((name, chunk))
    for name, _start, _end, chunk in arrow_rows:
        categorized.setdefault(_category(name), []).append((name, chunk))

    panel_names = ("core", "creation", "quality", "audio", "delivery", "trust", "continuity", "jobs", "maintenance")
    entry_imports = ["import './state.js';"]
    module_paths = ["state.js"]
    for panel in panel_names:
        rows = categorized.get(panel, [])
        directory = panels / panel
        directory.mkdir()
        groups = _pack(rows, target_lines)
        imports: list[str] = []
        for part_index, group in enumerate(groups, start=1):
            relative = f"panels/{panel}/part-{part_index:03d}.js"
            imports.append(f"import './{panel}/part-{part_index:03d}.js';")
            module_paths.append(relative)
            outputs.append(_write(scripts / relative, _function_module(group)))
        aggregator = "\n".join(
            [
                *imports,
                f"export const panel = Object.freeze({{ id: '{panel}', moduleCount: {len(groups)} }});",
                f"globalThis.MusicForgePanels.{panel} = panel;",
            ]
        ) + "\n"
        aggregator_path = f"panels/{panel}.js"
        outputs.append(_write(scripts / aggregator_path, aggregator))
        module_paths.append(aggregator_path)
        entry_imports.append(f"import './{aggregator_path}';")

    program = """export const panel = Object.freeze({
  id: 'program',
  workspaceId: 'program-workspace',
  continuityReceiverId: 'continuity-receiver-program-id',
});
globalThis.MusicForgePanels.program = panel;
"""
    outputs.append(_write(panels / "program.js", program))
    module_paths.append("panels/program.js")
    entry_imports.append("import './panels/program.js';")

    remaining = [_dedent(line) if index not in removed else "" for index, line in enumerate(lines)]
    first_wiring = "\n".join(remaining[:6000]).strip() + "\n"
    second_wiring = "\n".join(remaining[6000:]).strip() + "\n"
    outputs.append(_write(scripts / "wiring-primary.js", first_wiring))
    outputs.append(_write(scripts / "wiring-secondary.js", second_wiring))
    module_paths.extend(("wiring-primary.js", "wiring-secondary.js"))
    entry_imports.extend(("import './wiring-primary.js';", "import './wiring-secondary.js';"))

    entry = "\n".join([*entry_imports, "export const studioPanels = globalThis.MusicForgePanels;"]) + "\n"
    path.write_text(entry, encoding="utf-8")
    outputs.append(path)
    module_paths.append("app.js")
    outputs.append(
        _write(
            scripts / "module-manifest.json",
            json.dumps(sorted(module_paths), ensure_ascii=True, indent=2) + "\n",
        )
    )
    return outputs


def _category(name: str) -> str:
    value = name.lower()
    if value in {"loadgahealth", "rendergahealth", "loadmaintenancestatus", "rendermaintenancestatus"}:
        return "maintenance"
    if "continuity" in value:
        return "continuity"
    if any(token in value for token in ("portfolio", "trust", "governance", "attestation")):
        return "trust"
    if any(token in value for token in ("audio", "mastering", "stem", "pitch")):
        return "audio"
    if any(token in value for token in ("distribution", "submission", "delivery", "rights", "format", "release", "signoff")):
        return "delivery"
    if any(token in value for token in ("acceptance", "planning", "review", "candidate", "quality")):
        return "quality"
    if any(token in value for token in ("project", "editor", "asset", "reference", "library", "context", "variation", "preset", "prompt")):
        return "creation"
    if any(token in value for token in ("job", "batch", "node", "runtime", "warning", "metric", "artifact")):
        return "jobs"
    return "core"


def _function_module(rows: list[tuple[str, list[str]]]) -> str:
    names = [name for name, _chunk in rows]
    body = "\n\n".join("\n".join(chunk) for _name, chunk in rows)
    return "\n\n".join(
        [
            body,
            "Object.assign(globalThis, { " + ", ".join(names) + " });",
            "export { " + ", ".join(names) + " };",
        ]
    ) + "\n"


def _pack(rows: list[tuple[str, list[str]]], target_lines: int) -> list[list[tuple[str, list[str]]]]:
    groups: list[list[tuple[str, list[str]]]] = []
    current: list[tuple[str, list[str]]] = []
    count = 0
    for row in rows:
        size = len(row[1]) + 3
        if current and count + size > target_lines:
            groups.append(current)
            current, count = [], 0
        current.append(row)
        count += size
    if current:
        groups.append(current)
    return groups


def _find_exact_line(lines: list[str], start: int, target: str) -> int:
    for index in range(start, len(lines)):
        if lines[index] == target:
            return index
    raise ValueError(f"Could not find closing line {target!r} after line {start + 1}")


def _dedent(line: str) -> str:
    return line[4:] if line.startswith("    ") else line


def _write(path: Path, source: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Split the Studio browser application into real ES modules.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--git-ref")
    parser.add_argument("--target-lines", type=int, default=850)
    args = parser.parse_args()
    root = args.root.resolve()
    path = root / "song_agent" / "interfaces" / "web" / "scripts" / "app.js"
    source = None
    if args.git_ref:
        source = subprocess.run(
            ["git", "show", f"{args.git_ref}:{path.relative_to(root).as_posix()}"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout
    outputs = split_web_app(path, source=source, target_lines=args.target_lines)
    print(f"web app: {len(outputs)} modules; entry={len(path.read_text(encoding='utf-8').splitlines())} lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
