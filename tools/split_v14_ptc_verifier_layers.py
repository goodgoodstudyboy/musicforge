from __future__ import annotations

import ast
from pathlib import Path

from migrate_v14_domains import _module_exports


SPECS = (
    (
        "public_trust_center_verifier",
        "public_trust_center_core_verifier",
        "verify_public_trust_center_package",
    ),
    (
        "public_trust_center_distribution_kit_verifier",
        "public_trust_center_distribution_kit_core_verifier",
        "verify_public_trust_center_distribution_kit_package",
    ),
)


def split(root: Path) -> int:
    directory = root / "song_agent" / "domains" / "trust"
    for wrapper_name, core_name, function_name in SPECS:
        core_path = directory / f"{core_name}.py"
        wrapper_path = directory / f"{wrapper_name}.py"
        exports = [
            name
            for name in _module_exports(core_path.read_text(encoding="utf-8"))
            if name != function_name
        ]
        rows = [
            "from __future__ import annotations\n",
            "\n",
            "from typing import Any as __Any\n",
            "\n",
            "from song_agent.domains.trust.public_trust_center_acceptance_board_signoff_verifier import verify_public_trust_center_acceptance_board_signoff_archive_package as __signoff_verify\n",
        ]
        if exports:
            rows.append(
                f"from song_agent.domains.trust.{core_name} import {', '.join(exports)}\n"
            )
        rows.extend(
            [
                f"from song_agent.domains.trust.{core_name} import {function_name} as __core_verify\n",
                "\n\n",
                f"def {function_name}(*args: __Any, **kwargs: __Any) -> dict[str, __Any]:\n",
                "    kwargs['_acceptance_board_signoff_verifier'] = __signoff_verify\n",
                "    return __core_verify(*args, **kwargs)\n",
            ]
        )
        source = "".join(rows)
        ast.parse(source, filename=str(wrapper_path))
        wrapper_path.write_text(source, encoding="utf-8")
        print(f"split verifier entrypoint: {wrapper_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(split(Path.cwd()))
