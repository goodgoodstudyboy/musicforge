# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import base64 as base64
import hashlib as hashlib
import json as json
import shutil as shutil
import zipfile as zipfile
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.quality.human_review_verifier import verify_human_review_pack as verify_human_review_pack
from song_agent.domains.quality.music_acceptance import AcceptanceNotFoundError as AcceptanceNotFoundError, AcceptanceStateError as AcceptanceStateError, AcceptanceStore as AcceptanceStore, AcceptanceValidationError as AcceptanceValidationError, listening_review_summary as listening_review_summary, stable_hash as stable_hash
from song_agent.domains.creation.music_health import music_health_summary as music_health_summary
from song_agent.domains.studio.projectio import read_json as read_json, slugify as slugify, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.quality.review_tasks import REVIEW_TASK_SCHEMA_VERSION as REVIEW_TASK_SCHEMA_VERSION, ReviewTask as ReviewTask, ReviewTaskStore as ReviewTaskStore

class _DeferredGlobal:
    def __init__(self, name: str) -> None:
        self.name = name


def _make_deferred_global(name: str) -> type[object]:
    base: type[object] = Exception if name.endswith("Error") else object
    return type(f"_DeferredGlobal_{name}", (base,), {"_deferred_global_name": name})


def _deferred_global_name(value: object) -> str | None:
    if isinstance(value, _DeferredGlobal):
        return value.name
    if isinstance(value, type):
        name = getattr(value, "_deferred_global_name", None)
        if isinstance(name, str):
            return name
    return None


def _resolve_bound_default(value: object, namespace: dict[str, object]) -> object:
    name = _deferred_global_name(value)
    if name is not None:
        return namespace.get(name, value)
    if isinstance(value, tuple):
        return tuple(_resolve_bound_default(item, namespace) for item in value)
    if isinstance(value, list):
        return [_resolve_bound_default(item, namespace) for item in value]
    if isinstance(value, dict):
        return {
            _resolve_bound_default(key, namespace): _resolve_bound_default(item, namespace)
            for key, item in value.items()
        }
    return value


def _bind_function_defaults(function: object, namespace: dict[str, object]) -> None:
    defaults = getattr(function, "__defaults__", None)
    if defaults:
        function.__defaults__ = tuple(_resolve_bound_default(item, namespace) for item in defaults)
    kwdefaults = getattr(function, "__kwdefaults__", None)
    if kwdefaults:
        function.__kwdefaults__ = {
            key: _resolve_bound_default(item, namespace)
            for key, item in kwdefaults.items()
        }


def _bind_class_bases(cls: type[object], namespace: dict[str, object]) -> None:
    bases = tuple(_resolve_bound_default(base, namespace) for base in cls.__bases__)
    if bases != cls.__bases__ and all(isinstance(base, type) for base in bases):
        try:
            cls.__bases__ = bases
        except TypeError:
            pass


def _bind_deferred_defaults(namespace: dict[str, object]) -> None:
    for value in list(globals().values()):
        if callable(value) and hasattr(value, "__defaults__"):
            _bind_function_defaults(value, namespace)
        if isinstance(value, type):
            _bind_class_bases(value, namespace)
            for member in vars(value).values():
                target = member
                if isinstance(member, (staticmethod, classmethod)):
                    target = member.__func__
                if callable(target) and hasattr(target, "__defaults__"):
                    _bind_function_defaults(target, namespace)

HumanReviewPackStore = _make_deferred_global('HumanReviewPackStore')
part = _make_deferred_global('part')

def bind_globals(namespace: dict[str, object]) -> None:
    global HumanReviewPackStore, part
    HumanReviewPackStore = namespace.get('HumanReviewPackStore', HumanReviewPackStore)
    part = namespace.get('part', part)
    _bind_deferred_defaults(namespace)


HUMAN_REVIEW_PACK_SCHEMA_VERSION = 1
HUMAN_REVIEW_IMPORT_SCHEMA_VERSION = 1
HUMAN_REVIEW_MANIFEST_SCHEMA_VERSION = 1
REVIEW_STATUSES = {"accepted", "needs_fix", "rejected", "waived"}
PACK_REQUIRED_FILES = {"manifest.json", "pack.json", "index.html", "response-template.json", "checksums.json", "README.txt"}
DANGEROUS_RESPONSE_KEYS = {"source_path", "local_path", "absolute_path", "file", "path", "api_key", "token", "access_token", "authorization", "secret", "password", "raw_provider_response"}




class HumanReviewPackError(ValueError):
    pass

class HumanReviewPackNotFoundError(HumanReviewPackError):
    pass

class HumanReviewPackValidationError(HumanReviewPackError):
    pass

class HumanReviewPackStateError(HumanReviewPackError):
    pass

def human_review_evidence_summary(store: AcceptanceStore, suite_id: str) -> DomainDocument:
    helper = HumanReviewPackStore(store)
    try:
        packs = helper.list_packs(suite_id)
        imports = helper.list_imports(suite_id)
    except (AcceptanceNotFoundError, HumanReviewPackError, OSError, ValueError):
        return {"status": "missing", "pack_count": 0, "import_count": 0}
    latest_pack = packs[0] if packs else {}
    latest_import = imports[0] if imports else {}
    summary = _as_document(latest_import.get("summary"))
    return sanitize_metadata(
        {
            "status": "imported" if latest_import else "packaged" if latest_pack else "missing",
            "pack_count": len(packs),
            "import_count": len(imports),
            "latest_pack_id": latest_pack.get("pack_id"),
            "latest_pack_status": latest_pack.get("status"),
            "latest_import_id": latest_import.get("import_id"),
            "accepted_count": summary.get("accepted_count", 0),
            "needs_fix_count": summary.get("needs_fix_count", 0),
            "rejected_count": summary.get("rejected_count", 0),
            "created_review_task_count": summary.get("created_review_task_count", 0),
        }
    )

def _verification_summary(report: DomainDocument) -> DomainDocument:
    summary = _as_document(report.get("summary"))
    return sanitize_metadata(
        {
            "status": report.get("status"),
            "suite_id": summary.get("suite_id"),
            "pack_id": summary.get("pack_id"),
            "case_count": summary.get("case_count", 0),
            "entry_count": summary.get("entry_count", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
            "verified_at": report.get("generated_at"),
        }
    )

def validate_pack_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("hrpack-") or not text.removeprefix("hrpack-").isdigit():
        raise HumanReviewPackValidationError("Invalid human review pack id.")
    return text

def validate_import_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("review-import-") or not text.removeprefix("review-import-").isdigit():
        raise HumanReviewPackValidationError("Invalid human review import id.")
    return text

def _pack_source_state(store: AcceptanceStore, suite: object) -> DomainDocument:
    cases = [
        _case_source_state(store, suite.suite_id, case.case_id)
        for case in sorted(store.list_cases(suite.suite_id), key=lambda item: item.case_id)
    ]
    return sanitize_metadata(
        {
            "suite_id": suite.suite_id,
            "name": suite.name,
            "mode": suite.mode,
            "profile_id": suite.profile_id,
            "songbook_id": suite.songbook_id,
            "songbook_version": suite.songbook_version,
            "min_rating": suite.min_rating,
            "require_audio_if_renderer_configured": suite.require_audio_if_renderer_configured,
            "require_manual_review": suite.require_manual_review,
            "allow_synthetic_review": suite.allow_synthetic_review,
            "release_ready_profile": suite.release_ready_profile,
            "cases": cases,
        }
    )

def _case_source_state(store: AcceptanceStore, suite_id: str, case_id: str) -> DomainDocument:
    case = store.get_case(suite_id, case_id)
    case_dir = store.case_dir(suite_id, case_id)
    return sanitize_metadata(
        {
            "case": {
                "case_id": case.case_id,
                "suite_id": case.suite_id,
                "name": case.name,
                "source_type": case.source_type,
                "song_id": case.song_id,
                "songbook_id": case.songbook_id,
                "songbook_version": case.songbook_version,
                "expectations": case.expectations,
                "request_summary": case.request_summary,
                "job_id": case.job_id,
                "project_id": case.project_id,
                "version_id": case.version_id,
                "artifacts": case.artifacts,
                "health_summary": case.health_summary,
                "created_at": case.created_at,
            },
            "health": store.read_health(suite_id, case_id, default={}),
            "midi_sha256": _sha256_file(case_dir / "song.mid") if (case_dir / "song.mid").exists() else "",
            "wav_sha256": _sha256_file(case_dir / "song.wav") if (case_dir / "song.wav").exists() else "",
        }
    )

def _ensure_review_song_id_matches_pack(case_id: str, review: DomainDocument, pack_case: DomainDocument) -> None:
    if "song_id" not in review:
        return
    review_song_id = "" if review.get("song_id") is None else str(review.get("song_id"))
    pack_song_id = "" if pack_case.get("song_id") is None else str(pack_case.get("song_id"))
    if review_song_id != pack_song_id:
        raise HumanReviewPackValidationError(f"{case_id} song_id does not match human review pack.")

def _response_template(pack: DomainDocument) -> DomainDocument:
    return sanitize_metadata(
        {
            "schema_version": 1,
            "suite_id": pack.get("suite_id"),
            "pack_id": pack.get("pack_id"),
            "pack_source_hash": pack.get("source_hash"),
            "reviewer": {"name": "", "organization": ""},
            "reviewed_at": "",
            "reviews": [
                {
                    "case_id": item.get("case_id"),
                    "song_id": item.get("song_id"),
                    "status": "",
                    "rating": 0,
                    "playback_confirmed": False,
                    "audio_mode": item.get("audio_mode") or "midi",
                    "notes": "",
                    "issues": [],
                    "tags": [],
                    "markers": [],
                }
                for item in pack.get("cases", [])
                if isinstance(item, dict)
            ],
        }
    )

def _index_html(pack: DomainDocument) -> str:
    pack_json = json.dumps(pack, ensure_ascii=False)
    template_json = json.dumps(_response_template(pack), ensure_ascii=False)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MusicForge Human Review Pack</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; color: #1f2933; background: #f8fafc; }}
main {{ max-width: 1100px; margin: 0 auto; }}
section {{ background: white; border: 1px solid #d9e2ec; border-radius: 8px; padding: 16px; margin: 12px 0; }}
label {{ display: block; font-size: 13px; font-weight: 600; margin: 10px 0 4px; }}
input, select, textarea {{ width: 100%; box-sizing: border-box; padding: 8px; border: 1px solid #bcccdc; border-radius: 6px; }}
textarea {{ min-height: 90px; }}
button {{ padding: 8px 12px; border: 1px solid #52606d; border-radius: 6px; background: #243b53; color: white; cursor: pointer; }}
audio {{ width: 100%; margin-top: 8px; }}
.meta {{ color: #52606d; font-size: 13px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 8px; }}
</style>
</head>
<body>
<main>
<h1>MusicForge Human Review Pack</h1>
<p class="meta">Suite {pack.get('suite_id')} / Pack {pack.get('pack_id')}</p>
<section>
<div class="grid">
<label>Reviewer name<input id="reviewerName" autocomplete="name"></label>
<label>Organization<input id="reviewerOrg"></label>
</div>
<button type="button" onclick="downloadResponse()">Download review response JSON</button>
</section>
<div id="cases"></div>
</main>
<script>
const PACK = {pack_json};
const TEMPLATE = {template_json};
const reviews = new Map(TEMPLATE.reviews.map(row => [row.case_id, row]));
function renderCases() {{
  const root = document.getElementById('cases');
  root.innerHTML = '';
  PACK.cases.forEach(item => {{
    const row = document.createElement('section');
    row.innerHTML = `
      <h2>${{item.name || item.case_id}}</h2>
      <p class="meta">${{item.song_id || ''}} ${{item.style || ''}}</p>
      <audio controls src="${{item.wav_path || item.midi_path}}"></audio>
      <label>Status<select data-field="status" data-case="${{item.case_id}}">
        <option value="">Select</option><option value="accepted">Accepted</option><option value="needs_fix">Needs fix</option><option value="rejected">Rejected</option><option value="waived">Waived</option>
      </select></label>
      <label>Rating<input data-field="rating" data-case="${{item.case_id}}" type="number" min="1" max="5" value="0"></label>
      <label><input data-field="playback_confirmed" data-case="${{item.case_id}}" type="checkbox" style="width:auto"> Playback confirmed</label>
      <label>Notes<textarea data-field="notes" data-case="${{item.case_id}}"></textarea></label>
      <label>Issues, comma separated<input data-field="issues" data-case="${{item.case_id}}"></label>
    `;
    root.appendChild(row);
  }});
}}
document.addEventListener('input', event => {{
  const target = event.target;
  const caseId = target.getAttribute('data-case');
  const field = target.getAttribute('data-field');
  if (!caseId || !field) return;
  const row = reviews.get(caseId);
  if (field === 'rating') row[field] = Number(target.value || 0);
  else if (field === 'playback_confirmed') row[field] = Boolean(target.checked);
  else if (field === 'issues') row[field] = String(target.value || '').split(',').map(x => x.trim()).filter(Boolean);
  else row[field] = target.value;
}});
function downloadResponse() {{
  const response = {{
    schema_version: 1,
    suite_id: PACK.suite_id,
    pack_id: PACK.pack_id,
    pack_source_hash: PACK.source_hash,
    reviewer: {{ name: document.getElementById('reviewerName').value, organization: document.getElementById('reviewerOrg').value }},
    reviewed_at: new Date().toISOString(),
    reviews: Array.from(reviews.values())
  }};
  const blob = new Blob([JSON.stringify(response, null, 2)], {{ type: 'application/json' }});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url; link.download = `${{PACK.suite_id}}-${{PACK.pack_id}}-review-response.json`; link.click();
  URL.revokeObjectURL(url);
}}
renderCases();
</script>
</body>
</html>
"""

def _readme_text(pack: DomainDocument) -> str:
    return (
        "MusicForge Human Review Pack\n\n"
        f"Suite: {pack.get('suite_id')}\n"
        f"Pack: {pack.get('pack_id')}\n"
        f"Cases: {pack.get('case_count')}\n\n"
        "Open index.html in a browser, listen to every case, then export the review response JSON.\n"
        "Do not edit manifest.json or pack.json by hand.\n"
    )

def _response_from_payload(payload: DomainDocument) -> DomainDocument:
    if isinstance(payload.get("response"), dict):
        return dict(payload["response"])
    if isinstance(payload.get("response_json"), dict):
        return dict(payload["response_json"])
    if isinstance(payload.get("response_base64"), str):
        try:
            raw = base64.b64decode(str(payload["response_base64"]), validate=True)
            value = json.loads(raw.decode("utf-8"))
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise HumanReviewPackValidationError(f"response_base64 is not valid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise HumanReviewPackValidationError("response_base64 must decode to a JSON object.")
        return value
    return dict(payload)

def _validate_markers(review: DomainDocument, pack_case: DomainDocument) -> None:
    markers = review.get("markers")
    if markers is None:
        return
    if not isinstance(markers, list):
        raise HumanReviewPackValidationError("markers must be a list.")
    duration_seconds = int(pack_case.get("duration_seconds") or 90)
    max_beat = max(4, duration_seconds * 4)
    for index, marker in enumerate(markers[:100]):
        if not isinstance(marker, dict):
            raise HumanReviewPackValidationError(f"markers[{index}] must be an object.")
        beat = marker.get("beat")
        if beat is not None:
            try:
                beat_value = float(beat)
            except (TypeError, ValueError) as exc:
                raise HumanReviewPackValidationError(f"markers[{index}].beat must be numeric.") from exc
            if beat_value < 0 or beat_value > max_beat:
                raise HumanReviewPackValidationError(f"markers[{index}].beat is outside the case duration.")

def _safe_markers(value: object) -> list[DomainDocument]:
    if not isinstance(value, list):
        return []
    rows = []
    for marker in value[:100]:
        if not isinstance(marker, dict):
            continue
        rows.append(
            sanitize_metadata(
                {
                    "beat": marker.get("beat"),
                    "time_seconds": marker.get("time_seconds"),
                    "severity": _safe_text(marker.get("severity"), 40) or "note",
                    "label": _safe_text(marker.get("label"), 120),
                    "note": _safe_text(marker.get("note"), 500),
                }
            )
        )
    return rows

def _dangerous_key_paths(value: object, *, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            child = f"{prefix}.{key_text}" if prefix else key_text
            if key_text.lower() in DANGEROUS_RESPONSE_KEYS:
                paths.append(child)
            paths.extend(_dangerous_key_paths(item, prefix=child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(_dangerous_key_paths(item, prefix=f"{prefix}[{index}]"))
    return paths

def _safe_case_artifact(case_dir: Path, filename: str) -> Path:
    if filename not in {"song.mid", "song.wav"}:
        raise HumanReviewPackValidationError("Unsupported case artifact.")
    base = case_dir.resolve()
    target = (base / filename).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise HumanReviewPackValidationError("Refusing to operate outside acceptance case directory.") from exc
    if target.is_symlink():
        raise HumanReviewPackValidationError("Refusing to package symlink case artifact.")
    return target

def _is_safe_relpath(value: str) -> bool:
    raw = str(value or "")
    if "\\" in raw or not raw or raw.endswith("/") or raw.startswith("/") or raw.startswith("//"):
        return False
    parts = raw.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return False
    if ":" in parts[0]:
        return False
    return True

def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _append_task_event(task_dir: Path, event_type: str, payload: DomainDocument, now: str) -> None:
    path = task_dir / "events.jsonl"
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(sanitize_metadata({"timestamp": now, "type": event_type, "payload": payload}), ensure_ascii=False) + "\n")

def _safe_text(value: object, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "")).strip()[:limit]

def _validate_suite_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("suite-") or not text.removeprefix("suite-").isdigit():
        raise HumanReviewPackValidationError("Invalid suite_id.")
    return text

def _validate_case_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("case-") or not text.removeprefix("case-").isdigit():
        raise HumanReviewPackValidationError("Invalid case_id.")
    return text
