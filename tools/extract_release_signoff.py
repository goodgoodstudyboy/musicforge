from __future__ import annotations

import argparse
import ast
import textwrap
from pathlib import Path


def extract_release_signoff(route_path: Path, application_path: Path) -> None:
    source = route_path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source, filename=str(route_path))
    route_class = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "DeliveryRoutes"
    )
    method = next(
        node
        for node in route_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "_handle_release_signoff"
    )
    method_source = textwrap.dedent(
        "\n".join(lines[method.lineno - 1 : int(method.end_lineno or method.lineno)])
    ).replace("def _handle_release_signoff(", "def execute(", 1)
    application = "\n\n".join(
        [
            "from __future__ import annotations",
            "from datetime import datetime, timezone\nfrom http import HTTPStatus\nfrom typing import Any",
            "from song_agent.audio_encoding import encoded_audio_gate, normalize_required_profiles",
            "from song_agent.release_export import (\n    build_release_export_zip,\n    read_release_export_manifest,\n    refresh_release_export_signoff_summary,\n)",
            "from song_agent.release_qa import (\n    build_release_signoff_record,\n    release_qa_allows_signoff,\n    release_signoff_summary,\n)",
            "from song_agent.releases import stable_hash",
            "def _utc_now() -> str:\n    return datetime.now(timezone.utc).isoformat()",
            "class ReleaseSignoffApplication:\n"
            "    def __init__(self, port: object) -> None:\n"
            "        self.port = port\n\n"
            "    def __getattr__(self, name: str) -> Any:\n"
            "        return getattr(self.port, name)\n\n"
            + textwrap.indent(method_source, "    "),
        ]
    ) + "\n"
    application_path.write_text(application, encoding="utf-8")

    replacement = [
        "    def _handle_release_signoff(self, method: str, release_id: str) -> None:",
        "        ReleaseSignoffApplication(self).execute(method, release_id)",
    ]
    updated = [
        *lines[: method.lineno - 1],
        *replacement,
        *lines[int(method.end_lineno or method.lineno) :],
    ]
    import_line = "from song_agent.application.release_signoff import ReleaseSignoffApplication"
    insert_at = next(index for index, line in enumerate(updated) if line.startswith("from .delivery_parts"))
    updated[insert_at:insert_at] = [import_line, ""]
    route_path.write_text("\n".join(updated) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Move Release signoff orchestration behind an application use-case.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    extract_release_signoff(
        root / "song_agent" / "interfaces" / "api" / "routes" / "delivery.py",
        root / "song_agent" / "application" / "release_signoff.py",
    )
    print("release signoff: interface delegated to application use-case")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
