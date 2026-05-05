from __future__ import annotations

import json
import mimetypes
import os
import shutil
import threading
import webbrowser
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
from urllib.parse import parse_qs

from song_agent import __version__
from song_agent.cli import generate_request
from song_agent.projectio import ProjectPaths, read_json, slugify, write_json
from song_agent.provider import (
    ProviderError,
    load_provider_config,
    provider_configured,
    reset_provider_config,
    save_provider_config_from_dict,
    test_provider_config,
)
from song_agent.runtime_views import (
    build_timeline_view,
    build_tracks_view,
    build_validator_view,
)
from song_agent.schemas.song import SongRequest
from song_agent.webui import panel_html


RUNS_DIR = Path("runs")


@dataclass
class JobState:
    job_id: str
    title: str
    output_dir: str
    status: str
    created_at: str
    updated_at: str
    step: str = "created"
    message: str = ""
    summary: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    attempt_count: int = 0
    cancel_requested: bool = False
    pause_requested: bool = False
    hidden: bool = False
    input_payload: dict[str, Any] = field(default_factory=dict)
    provider_snapshot: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    deleted: bool = False
    interrupted: bool = False
    last_seen_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobState":
        now = _utc_now()
        return cls(
            job_id=str(data["job_id"]),
            title=str(data.get("title", data["job_id"])),
            output_dir=str(data["output_dir"]),
            status=str(data.get("status", "completed")),
            created_at=str(data.get("created_at", now)),
            updated_at=str(data.get("updated_at", now)),
            step=str(data.get("step", "")),
            message=str(data.get("message", "")),
            summary=_dict_or_empty(data.get("summary")),
            error=None if data.get("error") is None else str(data.get("error")),
            attempt_count=int(data.get("attempt_count", 0) or 0),
            cancel_requested=bool(data.get("cancel_requested", False)),
            pause_requested=bool(data.get("pause_requested", False)),
            hidden=bool(data.get("hidden", False)),
            input_payload=_dict_or_empty(data.get("input_payload")),
            provider_snapshot=_dict_or_empty(data.get("provider_snapshot")),
            artifacts=_dict_or_empty(data.get("artifacts")),
            deleted=bool(data.get("deleted", False)),
            interrupted=bool(data.get("interrupted", False)),
            last_seen_at=None
            if data.get("last_seen_at") is None
            else str(data.get("last_seen_at")),
            started_at=None if data.get("started_at") is None else str(data.get("started_at")),
            finished_at=None if data.get("finished_at") is None else str(data.get("finished_at")),
        )


class JobStore:
    def __init__(self, runs_dir: Path = RUNS_DIR) -> None:
        self.runs_dir = runs_dir
        self.lock = threading.RLock()
        self.jobs: dict[str, JobState] = {}
        self.load_existing_jobs()

    def load_existing_jobs(self) -> None:
        if not self.runs_dir.exists():
            return
        for state_path in self.runs_dir.glob("*/data/job-state.json"):
            try:
                job = JobState.from_dict(read_json(state_path))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if job.status in {"queued", "running", "waiting_retry", "paused"}:
                job.status = "interrupted"
                job.step = "interrupted"
                job.message = "This job was interrupted by a previous server shutdown."
                job.error = "Job was running when the server stopped."
                job.interrupted = True
                job.updated_at = _utc_now()
                self._write_job(job)
            self.jobs[job.job_id] = job

    def list_jobs(self, include_hidden: bool = False) -> list[JobState]:
        with self.lock:
            return sorted(
                [
                    job
                    for job in self.jobs.values()
                    if include_hidden or not job.hidden
                ],
                key=lambda job: job.created_at,
                reverse=True,
            )

    def get_job(self, job_id: str) -> JobState | None:
        with self.lock:
            return self.jobs.get(job_id)

    def create_job(self, payload: dict[str, Any], start_immediately: bool = True) -> JobState:
        request = SongRequest.from_dict(payload)
        generation_mode = _generation_mode(payload)
        provider_snapshot: dict[str, Any]
        if generation_mode == "provider":
            provider_config, _sources = load_provider_config()
            provider_config.validate_ready_for_provider()
            provider_snapshot = provider_config.to_snapshot("provider", _utc_now())
        else:
            provider_snapshot = {"mode": "local", "summary": "Local deterministic composer"}
        with self.lock:
            run_dir = self._reserve_run_dir(request.title)
            job_id = run_dir.name
            now = _utc_now()
            job = JobState(
                job_id=job_id,
                title=request.title,
                output_dir=str(run_dir),
                status="queued",
                created_at=now,
                updated_at=now,
                step="queued",
                message="Queued for local deterministic generation.",
                input_payload=request.to_dict(),
                provider_snapshot=provider_snapshot,
            )
            self.jobs[job_id] = job
            self._write_job(job)

        if start_immediately:
            self.start_job(job_id)
        return job

    def start_job(self, job_id: str) -> bool:
        job = self.get_job(job_id)
        if job is None or job.status != "queued" or job.cancel_requested:
            return False
        thread = threading.Thread(
            target=self._run_job,
            args=(job_id,),
            name=f"musicforge-job-{job_id}",
            daemon=True,
        )
        thread.start()
        return True

    def hide_job(self, job_id: str, hidden: bool) -> JobState | None:
        job = self.get_job(job_id)
        if job is None:
            return None
        self._update_job(job, hidden=hidden)
        return job

    def cancel_job(self, job_id: str) -> tuple[JobState | None, HTTPStatus, str | None]:
        job = self.get_job(job_id)
        if job is None:
            return None, HTTPStatus.NOT_FOUND, "Job not found."
        if job.status == "queued":
            self._update_job(
                job,
                status="cancelled",
                step="cancelled",
                message="Job was cancelled before generation started.",
                cancel_requested=True,
            )
            return job, HTTPStatus.OK, None
        if job.status == "running":
            self._update_job(
                job,
                cancel_requested=True,
                message="Cancellation requested; job will stop at the next stage boundary.",
            )
            return job, HTTPStatus.OK, None
        if job.status == "cancelled":
            return job, HTTPStatus.OK, None
        return job, HTTPStatus.CONFLICT, f"Cannot cancel a {job.status} job."

    def delete_job(self, job_id: str) -> tuple[bool, HTTPStatus, str | None]:
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                return False, HTTPStatus.NOT_FOUND, "Job not found."
            if job.status == "running":
                return False, HTTPStatus.CONFLICT, "Cannot delete a running job. Cancel it first."
            try:
                run_dir = self._ensure_run_dir_is_safe(Path(job.output_dir))
            except ValueError as exc:
                return False, HTTPStatus.CONFLICT, str(exc)
            if run_dir.exists():
                shutil.rmtree(run_dir)
            self.jobs.pop(job_id, None)
            return True, HTTPStatus.OK, None

    def _run_job(self, job_id: str) -> None:
        job = self.get_job(job_id)
        if job is None:
            return

        request = SongRequest.from_dict(job.input_payload)
        provider_config = None
        provider_snapshot = job.provider_snapshot
        if provider_snapshot.get("mode") == "provider":
            provider_config, _sources = load_provider_config()
            provider_config.validate_ready_for_provider()
            write_json(
                Path(job.output_dir) / "data" / "provider-snapshot.json",
                provider_snapshot,
            )
        if job.cancel_requested:
            self._update_job(
                job,
                status="cancelled",
                step="cancelled",
                message="Job was cancelled before generation started.",
            )
            return
        self._update_job(
            job,
            status="running",
            step="generate",
            message="Generating song plan and MIDI.",
            attempt_count=job.attempt_count + 1,
            started_at=job.started_at or _utc_now(),
        )
        try:
            job = self.get_job(job_id)
            if job is None or job.cancel_requested:
                if job is not None:
                    self._update_job(
                        job,
                        status="cancelled",
                        step="cancelled",
                        message="Job was cancelled before generation started.",
                    )
                return
            plan_path, midi_path = generate_request(
                request,
                out_dir=Path(job.output_dir),
                force=False,
                provider_config=provider_config,
                provider_snapshot=provider_snapshot if provider_config is not None else None,
            )
            job = self.get_job(job_id)
            if job is None:
                return
            if job.cancel_requested:
                self._update_job(
                    job,
                    status="cancelled",
                    step="cancelled",
                    message="Job was cancelled after the generation stage.",
                    finished_at=_utc_now(),
                )
                return
            validator_report_path = Path(job.output_dir) / "data" / "validator-report.json"
            write_json(validator_report_path, _build_validator_report(plan_path, midi_path))
            summary = _build_summary(plan_path, midi_path)
            artifacts = {
                "request": str(Path(job.output_dir) / "data" / "request.json"),
                "song_plan": str(plan_path),
                "run_summary": str(Path(job.output_dir) / "data" / "run-summary.json"),
                "validator_report": str(validator_report_path),
                "job_state": str(Path(job.output_dir) / "data" / "job-state.json"),
                "events": str(Path(job.output_dir) / "logs" / "events.jsonl"),
                "midi": str(midi_path),
            }
            provider_snapshot_path = Path(job.output_dir) / "data" / "provider-snapshot.json"
            if provider_snapshot_path.exists():
                artifacts["provider_snapshot"] = str(provider_snapshot_path)
            self._update_job(
                job,
                status="completed",
                step="completed",
                message="Song generation completed.",
                summary=summary,
                error=None,
                finished_at=_utc_now(),
                artifacts=artifacts,
            )
        except Exception as exc:
            self._update_job(
                job,
                status="failed",
                step="failed",
                message="Song generation failed.",
                error=str(exc),
                finished_at=_utc_now(),
            )

    def _update_job(self, job: JobState, **changes: Any) -> None:
        with self.lock:
            for key, value in changes.items():
                setattr(job, key, value)
            job.updated_at = _utc_now()
            self.jobs[job.job_id] = job
            self._write_job(job)

    def _write_job(self, job: JobState) -> None:
        paths = ProjectPaths.create(Path(job.output_dir))
        write_json(paths.data / "job-state.json", job.to_dict())

    def _reserve_run_dir(self, title: str) -> Path:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        slug = slugify(title)
        for index in range(1, 10_000):
            name = slug if index == 1 else f"{slug}-{index}"
            candidate = self.runs_dir / name
            try:
                candidate.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                continue
            return candidate
        raise RuntimeError(f"Could not allocate a unique run directory for {title!r}.")

    def _ensure_run_dir_is_safe(self, run_dir: Path) -> Path:
        base = self.runs_dir.resolve()
        target = run_dir.resolve()
        if target == base:
            raise ValueError("Refusing to delete runs directory.")
        if base not in target.parents:
            raise ValueError("Refusing to delete outside runs directory.")
        return target


class MusicForgeHandler(BaseHTTPRequestHandler):
    server_version = "MusicForgeHTTP/0.1"

    def do_GET(self) -> None:
        self._handle_request("GET")

    def do_POST(self) -> None:
        self._handle_request("POST")

    def log_message(self, format: str, *args: Any) -> None:
        return

    @property
    def store(self) -> JobStore:
        return self.server.job_store  # type: ignore[attr-defined]

    def _handle_request(self, method: str) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            if method == "GET" and path == "/":
                self._send_html(panel_html())
                return
            if method == "GET" and path == "/api/info":
                self._send_json(api_info())
                return
            if method == "GET" and path == "/api/template":
                self._send_json(api_template())
                return
            if path == "/api/provider":
                self._handle_provider_route(method)
                return
            if path == "/api/provider/reset":
                self._handle_provider_reset(method)
                return
            if path == "/api/provider/test":
                self._handle_provider_test(method)
                return
            if path == "/api/jobs":
                if method == "GET":
                    query = parse_qs(parsed.query)
                    include_hidden = query.get("include_hidden", ["0"])[0] in {"1", "true", "yes"}
                    self._send_json(
                        {
                            "jobs": [
                                job.to_dict()
                                for job in self.store.list_jobs(include_hidden=include_hidden)
                            ]
                        }
                    )
                    return
                if method == "POST":
                    payload = self._read_json_body()
                    job = self.store.create_job(payload)
                    self._send_json(job.to_dict(), status=HTTPStatus.ACCEPTED)
                    return

            job_route = _match_job_route(path)
            if job_route is not None:
                job_id, tail = job_route
                self._handle_job_route(method, job_id, tail)
                return

            self._send_error(HTTPStatus.NOT_FOUND, "Route not found.")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ProviderError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except Exception as exc:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    def _handle_provider_route(self, method: str) -> None:
        if method == "GET":
            config, sources = load_provider_config()
            self._send_json(
                {
                    "configured": provider_configured(config),
                    "config": config.to_public_dict(sources),
                }
            )
            return
        if method == "POST":
            config = save_provider_config_from_dict(self._read_json_body())
            self._send_json(
                {
                    "ok": True,
                    "configured": provider_configured(config),
                    "config": config.to_public_dict(),
                }
            )
            return
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_provider_reset(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        reset_provider_config()
        config, _sources = load_provider_config()
        self._send_json({"ok": True, "configured": provider_configured(config)})

    def _handle_provider_test(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        config, _sources = load_provider_config()
        self._send_json(test_provider_config(config))

    def _handle_job_route(self, method: str, job_id: str, tail: str) -> None:
        job = self.store.get_job(job_id)
        if job is None:
            self._send_error(HTTPStatus.NOT_FOUND, "Job not found.")
            return

        run_dir = Path(job.output_dir)
        if tail == "/open-folder":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            open_folder(run_dir)
            self._send_json({"ok": True, "path": str(run_dir)})
            return
        if tail in {"/hide", "/unhide"}:
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            job = self.store.hide_job(job_id, hidden=tail == "/hide")
            if job is None:
                self._send_error(HTTPStatus.NOT_FOUND, "Job not found.")
                return
            self._send_json({"ok": True, "job": job.to_dict()})
            return
        if tail == "/cancel":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            job, status, error = self.store.cancel_job(job_id)
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, "job": job.to_dict() if job is not None else None})
            return
        if tail == "/delete":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            deleted, status, error = self.store.delete_job(job_id)
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, "deleted": deleted, "job_id": job_id})
            return

        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return

        if tail == "":
            self._send_json(job.to_dict())
            return
        if tail == "/song-plan":
            plan_path = run_dir / "data" / "song-plan.json"
            if not plan_path.exists():
                self._send_error(
                    HTTPStatus.CONFLICT,
                    "song-plan.json is not available for this job yet.",
                )
                return
            self._send_json(read_json(plan_path))
            return
        if tail == "/timeline":
            self._send_runtime_view(job, "timeline")
            return
        if tail == "/tracks":
            self._send_runtime_view(job, "tracks")
            return
        if tail == "/validator":
            self._send_runtime_view(job, "validator")
            return
        if tail == "/events":
            self._send_json({"events": _read_events(run_dir / "logs" / "events.jsonl")})
            return
        if tail == "/artifacts":
            self._send_json({"artifacts": discover_artifacts(run_dir)})
            return
        if tail == "/midi":
            self._send_file(run_dir / "renders" / "song.mid", "audio/midi")
            return

        self._send_error(HTTPStatus.NOT_FOUND, "Job route not found.")

    def _send_runtime_view(self, job: JobState, view_name: str) -> None:
        run_dir = Path(job.output_dir)
        plan_path = run_dir / "data" / "song-plan.json"
        validator_path = run_dir / "data" / "validator-report.json"
        if view_name in {"timeline", "tracks"} and not plan_path.exists():
            self._send_error(
                HTTPStatus.CONFLICT,
                "song-plan.json is not available for this job yet.",
            )
            return

        if view_name == "validator":
            report = read_json(validator_path) if validator_path.exists() else None
            self._send_json(
                {
                    "job_id": job.job_id,
                    "view": build_validator_view(report),
                }
            )
            return

        plan = read_json(plan_path)
        if view_name == "timeline":
            view = build_timeline_view(plan)
        elif view_name == "tracks":
            view = build_tracks_view(plan)
        else:
            self._send_error(HTTPStatus.NOT_FOUND, "Runtime view not found.")
            return
        self._send_json({"job_id": job.job_id, "view": view})

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        if not body:
            raise ValueError("Request body must be JSON.")
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object.")
        return data

    def _send_json(self, data: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str | None = None) -> None:
        if not path.exists() or not path.is_file():
            self._send_error(HTTPStatus.NOT_FOUND, "File not found.")
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK.value)
        self.send_header(
            "Content-Type",
            content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        )
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: HTTPStatus, message: str) -> None:
        self._send_json({"error": message}, status=status)


def create_server(host: str = "127.0.0.1", port: int = 8787) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), MusicForgeHandler)
    server.job_store = JobStore()  # type: ignore[attr-defined]
    return server


def serve(host: str = "127.0.0.1", port: int = 8787) -> None:
    server = create_server(host, port)
    url = f"http://{host}:{port}"
    print(f"MusicForge Studio running at {url}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping MusicForge Studio.")
    finally:
        server.server_close()


def api_info() -> dict[str, Any]:
    return {
        "app": "MusicForge",
        "version": __version__,
        "cwd": str(Path.cwd()),
        "runs_dir": str(RUNS_DIR),
        "mode": "local-deterministic",
        "provider": {"enabled": False, "summary": "Local deterministic composer"},
    }


def api_template() -> dict[str, Any]:
    return {
        "defaults": {
            "title": "Rainy Convenience Store",
            "language": "zh",
            "style": "city pop, soft rock, warm synths, clean electric guitar",
            "theme": "a person remembers an old friend during a rainy night in the city",
            "duration_seconds": 180,
            "vocal_mode": "guide_melody",
            "tempo_bpm": 92,
            "key": "C major",
        },
        "presets": [
            {
                "name": "City Pop 120s",
                "style": "city pop, soft rock, warm synths, clean electric guitar",
                "duration_seconds": 120,
                "tempo_bpm": 92,
                "key": "C major",
            },
            {
                "name": "Lo-fi Loop 60s",
                "style": "lo-fi hip hop, mellow keys, dusty drums",
                "duration_seconds": 60,
                "tempo_bpm": 78,
                "key": "A minor",
            },
            {
                "name": "Game Battle Loop 45s",
                "style": "game battle loop, synth bass, tight drums",
                "duration_seconds": 45,
                "tempo_bpm": 132,
                "key": "D minor",
            },
        ],
    }


def discover_artifacts(run_dir: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_file():
            artifacts.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "kind": _artifact_kind(path),
                    "size": path.stat().st_size,
                }
            )
    return artifacts


def open_folder(path: Path) -> None:
    if os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]
        return
    webbrowser.open(path.resolve().as_uri())


def _build_summary(plan_path: Path, midi_path: Path) -> dict[str, Any]:
    plan = read_json(plan_path)
    tracks = plan.get("tracks", [])
    sections = plan.get("sections", [])
    return {
        "title": plan.get("title"),
        "tempo_bpm": plan.get("tempo_bpm"),
        "key": plan.get("key"),
        "meter": plan.get("meter"),
        "section_count": len(sections),
        "track_count": len(tracks),
        "note_count": sum(len(track.get("notes", [])) for track in tracks),
        "midi_size": midi_path.stat().st_size if midi_path.exists() else 0,
    }


def _build_validator_report(plan_path: Path, midi_path: Path) -> dict[str, Any]:
    plan = read_json(plan_path)
    return {
        "status": "passed",
        "checks": [
            "song_request_schema",
            "song_plan_schema",
            "song_plan_validation",
            "midi_render",
        ],
        "title": plan.get("title"),
        "midi_path": str(midi_path),
        "midi_exists": midi_path.exists(),
        "midi_size": midi_path.stat().st_size if midi_path.exists() else 0,
        "checked_at": _utc_now(),
    }


def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def _match_job_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/jobs/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if "/" in rest:
        job_id, tail = rest.split("/", 1)
        return unquote(job_id), "/" + tail
    return unquote(rest), ""


def _artifact_kind(path: Path) -> str:
    if path.suffix == ".json":
        return "json"
    if path.suffix == ".jsonl":
        return "events"
    if path.suffix == ".mid":
        return "midi"
    return "file"


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _generation_mode(payload: dict[str, Any]) -> str:
    mode = str(payload.get("generation_mode", "local") or "local")
    if mode not in {"local", "provider"}:
        raise ValueError("generation_mode must be either local or provider.")
    return mode


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
