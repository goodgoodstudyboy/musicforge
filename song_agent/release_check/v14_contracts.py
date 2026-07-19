from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from song_agent.interfaces.api.router import api_inventory
from song_agent.interfaces.cli.app import REGISTRY, command_inventory
from song_agent.persistence_cli import build_parser as build_state_parser
from song_agent.release_check_interfaces import (
    EXPECTED_COMMAND_HELP_HASH,
    EXPECTED_COMMAND_INVENTORY_HASH,
    EXPECTED_PANEL_HASH,
    EXPECTED_ROUTE_INVENTORY_HASH,
    _hash_json,
    command_help_contract_rows,
)
from song_agent.platform.verification.hashing import integrity_hash, integrity_ok


V138_FINAL_SHA = "98a7b25cbe505dca9f2f3ab946951adf3ebd1b2a"
CONTRACT_PATH = "architecture-v14-public-contracts.json"
EXPECTED_V138_WEB_CONTRACT_HASH = "386c5cf651ba18536a1073dc0557fffe749524c80491f6b4c68df74da5a2877a"
EXPECTED_V138_STATE_CLI_HASH = "e132bf91368d8ea720b53dcdc9ddfa60087856c9ee097c5ce6f4ce65d0e4a57c"
V14_STATE_ADDITIONS = ("v14-apply", "v14-plan", "v14-rollback", "v14-rollback-rehearsal")
_CONTROL_ID = re.compile(r"\bid=[\"']([^\"']+)[\"']")
_DOM_ID = re.compile(r"(?:getElementById|querySelector)\(\s*[`\"']#?([A-Za-z][A-Za-z0-9_.:-]*)")
_API_LITERAL = re.compile(r"/api/[A-Za-z0-9_./${}:?-]+")


def collect_current_contracts(root: Path) -> DomainDocument:
    commands = command_inventory()
    parsers = command_help_contract_rows(REGISTRY)
    state_actions = _state_cli_contract()
    routes = api_inventory()
    web = _current_web_contract(root)
    return {
        "cli": {
            "command_count": len(commands),
            "command_names": sorted(str(row["name"]) for row in commands),
            "inventory_hash": _hash_json(commands),
            "parser_contract_hash": _hash_json(parsers),
            "exit_code_policies": sorted({str(row["exit_code_policy"]) for row in commands}),
            "redaction_policy": "sanitize_sensitive_text",
            "state_actions": state_actions,
            "state_action_contract_hash": _hash_json(state_actions),
        },
        "api": {
            "route_count": len(routes),
            "route_keys": sorted(f"{row['method']} {row['pattern']}" for row in routes),
            "route_contract_hash": _hash_json(routes),
            "auth_policies": sorted({str(row["auth"]) for row in routes}),
        },
        "web": web,
    }


def collect_v138_contracts(root: Path) -> DomainDocument:
    web = _tag_web_contract(root, "v13.8.0")
    current = collect_current_contracts(root)
    state_actions = [row for row in current["cli"]["state_actions"] if row["name"] not in V14_STATE_ADDITIONS]
    return {
        "cli": {
            **current["cli"],
            "inventory_hash": EXPECTED_COMMAND_INVENTORY_HASH,
            "parser_contract_hash": EXPECTED_COMMAND_HELP_HASH,
            "state_actions": state_actions,
            "state_action_contract_hash": _hash_json(state_actions),
        },
        "api": {
            **current["api"],
            "route_contract_hash": EXPECTED_ROUTE_INVENTORY_HASH,
        },
        "web": web,
    }


def build_v14_contract_document(root: Path) -> DomainDocument:
    baseline = collect_v138_contracts(root)
    current = collect_current_contracts(root)
    diffs = _contract_diffs(baseline, current)
    document = {
        "schema_version": 1,
        "package_type": "musicforge_v14_public_contract_policy",
        "release_version": "14.0.0",
        "baseline": {"tag": "v13.8.0", "sha": V138_FINAL_SHA, "contracts": baseline},
        "current": current,
        "diffs": diffs,
        "allowed_breaking_changes": [],
        "allowed_additive_changes": {"state_cli_actions": list(V14_STATE_ADDITIONS)},
        "status": "passed" if not any(diffs.values()) else "failed",
    }
    document["integrity_hash"] = integrity_hash(document)
    return document


def verify_v14_public_contracts(
    root: Path,
    *,
    policy_path: Path | None = None,
) -> DomainDocument:
    path = policy_path or root / CONTRACT_PATH
    blockers: list[str] = []
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {"status": "failed", "blockers": ["v14_contract_policy_readable"]}
    if not isinstance(policy, dict):
        return {"status": "failed", "blockers": ["v14_contract_policy_object"]}
    if not integrity_ok(policy):
        blockers.append("v14_contract_policy_integrity")
    if policy.get("package_type") != "musicforge_v14_public_contract_policy":
        blockers.append("v14_contract_policy_type")
    baseline = policy.get("baseline") or {}
    if baseline.get("tag") != "v13.8.0" or baseline.get("sha") != V138_FINAL_SHA:
        blockers.append("v14_contract_baseline_identity")
    baseline_contracts = baseline.get("contracts") or {}
    _check_baseline_hashes(baseline_contracts, blockers)
    current = collect_current_contracts(root)
    if policy.get("current") != current:
        blockers.append("v14_contract_current_snapshot")
    diffs = _contract_diffs(baseline_contracts, current)
    for group, values in diffs.items():
        if values:
            blockers.append(f"v14_contract_{group}_compatibility")
    if policy.get("diffs") != diffs:
        blockers.append("v14_contract_diff_binding")
    if policy.get("allowed_breaking_changes"):
        blockers.append("v14_contract_unplanned_breaking_change")
    if policy.get("allowed_additive_changes") != {"state_cli_actions": list(V14_STATE_ADDITIONS)}:
        blockers.append("v14_contract_additive_change_policy")
    if policy.get("status") != "passed":
        blockers.append("v14_contract_policy_status")
    return {
        "schema_version": 1,
        "package_type": "musicforge_v14_public_contract_verification",
        "status": "passed" if not blockers else "failed",
        "blockers": blockers,
        "summary": {
            "command_count": current["cli"]["command_count"],
            "route_count": current["api"]["route_count"],
            "web_control_count": current["web"]["control_count"],
            "web_endpoint_count": current["web"]["endpoint_count"],
        },
    }


def _check_baseline_hashes(contracts: ImplementationDocument, blockers: list[str]) -> None:
    cli = contracts.get("cli") or {}
    api = contracts.get("api") or {}
    web = contracts.get("web") or {}
    if cli.get("inventory_hash") != EXPECTED_COMMAND_INVENTORY_HASH:
        blockers.append("v14_contract_baseline_cli_inventory")
    if cli.get("parser_contract_hash") != EXPECTED_COMMAND_HELP_HASH:
        blockers.append("v14_contract_baseline_cli_parser")
    if EXPECTED_V138_STATE_CLI_HASH and cli.get("state_action_contract_hash") != EXPECTED_V138_STATE_CLI_HASH:
        blockers.append("v14_contract_baseline_state_cli")
    if api.get("route_contract_hash") != EXPECTED_ROUTE_INVENTORY_HASH:
        blockers.append("v14_contract_baseline_api_routes")
    if web.get("panel_html_hash") != EXPECTED_PANEL_HASH:
        blockers.append("v14_contract_baseline_web_panel")
    if EXPECTED_V138_WEB_CONTRACT_HASH and web.get("contract_hash") != EXPECTED_V138_WEB_CONTRACT_HASH:
        blockers.append("v14_contract_baseline_web_contract")


def _contract_diffs(baseline: ImplementationDocument, current: ImplementationDocument) -> dict[str, list[str]]:
    cli_base = baseline.get("cli") or {}
    cli_current = current.get("cli") or {}
    api_base = baseline.get("api") or {}
    api_current = current.get("api") or {}
    web_base = baseline.get("web") or {}
    web_current = current.get("web") or {}
    cli = []
    if cli_base.get("inventory_hash") != cli_current.get("inventory_hash"):
        cli.append("command_inventory")
    if cli_base.get("parser_contract_hash") != cli_current.get("parser_contract_hash"):
        cli.append("parser_contract")
    baseline_state = {row["name"]: row for row in cli_base.get("state_actions") or []}
    current_state = {row["name"]: row for row in cli_current.get("state_actions") or []}
    if any(current_state.get(name) != row for name, row in baseline_state.items()):
        cli.append("state_cli_contract")
    if sorted(set(current_state) - set(baseline_state)) != list(V14_STATE_ADDITIONS):
        cli.append("state_cli_additions")
    api = [] if api_base.get("route_contract_hash") == api_current.get("route_contract_hash") else ["route_contract"]
    web = []
    for field in ("control_ids", "api_endpoints", "modules"):
        if web_base.get(field) != web_current.get(field):
            web.append(field)
    return {"cli": cli, "api": api, "web": web}


def _current_web_contract(root: Path) -> ImplementationDocument:
    web_root = root / "song_agent" / "interfaces" / "web"
    modules = json.loads((web_root / "scripts" / "module-manifest.json").read_text(encoding="utf-8"))
    sources = [(web_root / "index.html").read_text(encoding="utf-8")]
    sources.extend((web_root / "scripts" / str(module)).read_text(encoding="utf-8") for module in modules)
    panel_hash = hashlib.sha256(
        (web_root / "index.html").read_text(encoding="utf-8").replace(
            "{{MUSICFORGE_STYLES}}", (web_root / "styles" / "studio.css").read_text(encoding="utf-8")
        ).replace(
            "{{MUSICFORGE_SCRIPTS}}", '<script type="module" src="/assets/musicforge/app.js"></script>'
        ).encode("utf-8")
    ).hexdigest()
    return _web_contract(sources, [str(value) for value in modules], panel_hash)


def _state_cli_contract() -> list[ImplementationDocument]:
    parser = build_state_parser()
    subparsers = next(
        action for action in parser._actions if action.__class__.__name__ == "_SubParsersAction"
    )
    rows = []
    for name, child in sorted(subparsers.choices.items()):
        rows.append(
            {
                "name": name,
                "actions": [
                    {
                        "action_class": action.__class__.__name__,
                        "option_strings": list(action.option_strings),
                        "dest": action.dest,
                        "required": bool(action.required),
                        "nargs": _simple_value(action.nargs),
                        "default": _simple_value(action.default),
                        "choices": _simple_value(list(action.choices) if action.choices is not None else None),
                    }
                    for action in child._actions
                ],
            }
        )
    return rows


def _simple_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_simple_value(item) for item in value]
    return str(value)


def _tag_web_contract(root: Path, tag: str) -> ImplementationDocument:
    prefix = "song_agent/interfaces/web/"
    manifest = json.loads(_git_show(root, tag, prefix + "scripts/module-manifest.json"))
    sources = [_git_show(root, tag, prefix + "index.html")]
    sources.extend(_git_show(root, tag, prefix + "scripts/" + str(module)) for module in manifest)
    index = sources[0]
    panel = index.replace("{{MUSICFORGE_STYLES}}", _git_show(root, tag, prefix + "styles/studio.css")).replace(
        "{{MUSICFORGE_SCRIPTS}}", '<script type="module" src="/assets/musicforge/app.js"></script>'
    )
    return _web_contract(sources, [str(value) for value in manifest], hashlib.sha256(panel.encode("utf-8")).hexdigest())


def _web_contract(sources: list[str], modules: list[str], panel_hash: str) -> ImplementationDocument:
    source = "\n".join(sources)
    controls = sorted(set(_CONTROL_ID.findall(source)) | set(_DOM_ID.findall(source)))
    endpoints = sorted(set(_API_LITERAL.findall(source)))
    payload = {"control_ids": controls, "api_endpoints": endpoints, "modules": sorted(modules)}
    return {
        **payload,
        "control_count": len(controls),
        "endpoint_count": len(endpoints),
        "module_count": len(modules),
        "panel_html_hash": panel_hash,
        "contract_hash": _hash_json(payload),
    }


def _git_show(root: Path, tag: str, path: str) -> str:
    completed = subprocess.run(
        ["git", "show", f"{tag}:{path}"], cwd=root, capture_output=True, check=True
    )
    return completed.stdout.decode("utf-8")


def run_v14_public_contract_compatibility_smoke(root: Path) -> tuple[bool, str]:
    report = verify_v14_public_contracts(root)
    return report["status"] == "passed", json.dumps(report, sort_keys=True)
