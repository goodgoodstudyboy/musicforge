from __future__ import annotations

import csv
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

from .projectio import read_json, slugify, write_json
from .schemas.song import SongRequest


BATCH_ROOT = Path(".musicforge") / "batches"

BATCH_STATUSES = {
    "draft",
    "queued",
    "running",
    "paused",
    "completed",
    "completed_with_errors",
    "cancelled",
    "failed",
}
ITEM_STATUSES = {
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
    "skipped",
}

REQUIRED_CSV_COLUMNS = ("title", "language", "style", "theme")
CSV_COLUMNS = (
    "title",
    "language",
    "style",
    "theme",
    "duration_seconds",
    "tempo_bpm",
    "key",
    "vocal_mode",
    "lyrics",
    "generation_mode",
    "pipeline_mode",
)
GENERATION_MODES = {"local", "provider"}
PIPELINE_MODES = {"single", "multinode"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def validate_generation_mode(value: str) -> str:
    value = _clean(value) or "local"
    if value not in GENERATION_MODES:
        raise ValueError(f"generation_mode must be one of: {', '.join(sorted(GENERATION_MODES))}.")
    return value


def validate_pipeline_mode(value: str) -> str:
    value = _clean(value) or "multinode"
    if value not in PIPELINE_MODES:
        raise ValueError(f"pipeline_mode must be one of: {', '.join(sorted(PIPELINE_MODES))}.")
    return value


def validate_max_concurrency(value: Any) -> int:
    try:
        concurrency = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("max_concurrency must be an integer between 1 and 4.") from exc
    if concurrency < 1 or concurrency > 4:
        raise ValueError("max_concurrency must be between 1 and 4.")
    return concurrency


def _parse_int_field(row_number: int, field_name: str, value: Any, *, default: int | None = None) -> int | None:
    text = _clean(value)
    if not text:
        return default
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"CSV row {row_number} has invalid integer field: {field_name}.") from exc


def _validate_duration(row_number: int, value: Any) -> int:
    duration = _parse_int_field(row_number, "duration_seconds", value, default=180)
    assert duration is not None
    if duration < 30 or duration > 600:
        raise ValueError(f"CSV row {row_number} duration_seconds must be between 30 and 600.")
    return duration


def _validate_tempo(row_number: int, value: Any) -> int | None:
    tempo = _parse_int_field(row_number, "tempo_bpm", value, default=None)
    if tempo is not None and (tempo < 40 or tempo > 240):
        raise ValueError(f"CSV row {row_number} tempo_bpm must be between 40 and 240.")
    return tempo


@dataclass
class BatchState:
    batch_id: str
    name: str
    status: str = "draft"
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    source: str = "csv"
    max_concurrency: int = 1
    generation_mode: str = "local"
    pipeline_mode: str = "multinode"
    hidden: bool = False
    total_count: int = 0
    queued_count: int = 0
    running_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    cancelled_count: int = 0
    skipped_count: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "name": self.name,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source": self.source,
            "max_concurrency": self.max_concurrency,
            "generation_mode": self.generation_mode,
            "pipeline_mode": self.pipeline_mode,
            "hidden": self.hidden,
            "total_count": self.total_count,
            "queued_count": self.queued_count,
            "running_count": self.running_count,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "cancelled_count": self.cancelled_count,
            "skipped_count": self.skipped_count,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BatchState":
        created_at = data.get("created_at") or now_iso()
        return cls(
            batch_id=str(data["batch_id"]),
            name=str(data.get("name") or data["batch_id"]),
            status=str(data.get("status") or "draft"),
            created_at=created_at,
            updated_at=str(data.get("updated_at") or created_at),
            source=str(data.get("source") or "csv"),
            max_concurrency=validate_max_concurrency(data.get("max_concurrency", 1)),
            generation_mode=validate_generation_mode(str(data.get("generation_mode") or "local")),
            pipeline_mode=validate_pipeline_mode(str(data.get("pipeline_mode") or "multinode")),
            hidden=bool(data.get("hidden", False)),
            total_count=int(data.get("total_count", 0)),
            queued_count=int(data.get("queued_count", 0)),
            running_count=int(data.get("running_count", 0)),
            completed_count=int(data.get("completed_count", 0)),
            failed_count=int(data.get("failed_count", 0)),
            cancelled_count=int(data.get("cancelled_count", 0)),
            skipped_count=int(data.get("skipped_count", 0)),
            error=data.get("error"),
        )


@dataclass
class BatchItem:
    item_id: str
    index: int
    request: dict[str, Any]
    status: str = "queued"
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    job_id: str | None = None
    output_dir: str | None = None
    error: str | None = None
    attempt_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "index": self.index,
            "request": self.request,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "job_id": self.job_id,
            "output_dir": self.output_dir,
            "error": self.error,
            "attempt_count": self.attempt_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BatchItem":
        created_at = data.get("created_at") or now_iso()
        return cls(
            item_id=str(data["item_id"]),
            index=int(data["index"]),
            request=dict(data.get("request") or {}),
            status=str(data.get("status") or "queued"),
            created_at=created_at,
            updated_at=str(data.get("updated_at") or created_at),
            job_id=data.get("job_id"),
            output_dir=data.get("output_dir"),
            error=data.get("error"),
            attempt_count=int(data.get("attempt_count", 0)),
        )


@dataclass
class BatchDocument:
    state: BatchState
    items: list[BatchItem]

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch": self.state.to_dict(),
            "items": [item.to_dict() for item in self.items],
        }


def recalculate_counts(document: BatchDocument, *, touch: bool = False) -> None:
    counts = {status: 0 for status in ITEM_STATUSES}
    for item in document.items:
        counts[item.status] = counts.get(item.status, 0) + 1

    document.state.total_count = len(document.items)
    document.state.queued_count = counts.get("queued", 0)
    document.state.running_count = counts.get("running", 0)
    document.state.completed_count = counts.get("completed", 0)
    document.state.failed_count = counts.get("failed", 0)
    document.state.cancelled_count = counts.get("cancelled", 0)
    document.state.skipped_count = counts.get("skipped", 0)
    if touch:
        document.state.updated_at = now_iso()


class BatchStore:
    def __init__(self, root: Path | str = BATCH_ROOT):
        self.root = Path(root)

    def import_csv(
        self,
        *,
        name: str,
        csv_text: str,
        generation_mode: str = "local",
        pipeline_mode: str = "multinode",
        max_concurrency: int | str = 1,
    ) -> BatchDocument:
        name = _clean(name) or "Untitled Batch"
        generation_mode = validate_generation_mode(generation_mode)
        pipeline_mode = validate_pipeline_mode(pipeline_mode)
        max_concurrency = validate_max_concurrency(max_concurrency)
        items = parse_batch_csv(
            csv_text,
            generation_mode=generation_mode,
            pipeline_mode=pipeline_mode,
        )

        batch_dir = self._reserve_batch_dir(name)
        state = BatchState(
            batch_id=batch_dir.name,
            name=name,
            max_concurrency=max_concurrency,
            generation_mode=generation_mode,
            pipeline_mode=pipeline_mode,
        )
        document = BatchDocument(state=state, items=items)
        recalculate_counts(document)
        self.save_batch(document)
        self.append_event(document.state.batch_id, "batch_imported", {"item_count": len(items)})
        return document

    def list_batches(self, *, include_hidden: bool = False) -> list[BatchDocument]:
        documents: list[BatchDocument] = []
        for batch_json in self.root.glob("*/batch.json"):
            try:
                document = self.get_batch(batch_json.parent.name)
            except (FileNotFoundError, ValueError):
                continue
            if document.state.hidden and not include_hidden:
                continue
            documents.append(document)
        return sorted(documents, key=lambda doc: doc.state.created_at, reverse=True)

    def get_batch(self, batch_id: str) -> BatchDocument:
        batch_dir = self.batch_dir(batch_id)
        batch_json = batch_dir / "batch.json"
        items_json = batch_dir / "items.json"
        if not batch_json.exists() or not items_json.exists():
            raise FileNotFoundError(batch_id)
        state = BatchState.from_dict(read_json(batch_json))
        items_data = read_json(items_json)
        raw_items = items_data.get("items", items_data) if isinstance(items_data, dict) else items_data
        items = [BatchItem.from_dict(item) for item in raw_items]
        document = BatchDocument(state=state, items=items)
        recalculate_counts(document)
        return document

    def save_batch(self, document: BatchDocument) -> None:
        if document.state.status not in BATCH_STATUSES:
            raise ValueError(f"Unsupported batch status: {document.state.status}.")
        for item in document.items:
            if item.status not in ITEM_STATUSES:
                raise ValueError(f"Unsupported batch item status: {item.status}.")
        recalculate_counts(document, touch=True)
        batch_dir = self.batch_dir(document.state.batch_id)
        batch_dir.mkdir(parents=True, exist_ok=True)
        write_json(batch_dir / "batch.json", document.state.to_dict())
        write_json(batch_dir / "items.json", {"items": [item.to_dict() for item in document.items]})

    def update_item(self, batch_id: str, item: BatchItem) -> BatchDocument:
        document = self.get_batch(batch_id)
        for index, existing in enumerate(document.items):
            if existing.item_id == item.item_id:
                item.updated_at = now_iso()
                document.items[index] = item
                self.save_batch(document)
                return document
        raise FileNotFoundError(item.item_id)

    def export_batch(self, batch_id: str) -> dict[str, Any]:
        document = self.get_batch(batch_id)
        export = {
            "batch": document.state.to_dict(),
            "items": [self._export_item(item) for item in document.items],
            "generated_at": now_iso(),
        }
        write_json(self.batch_dir(batch_id) / "export.json", export)
        self.append_event(batch_id, "batch_exported", {"item_count": len(document.items)})
        return export

    def hide_batch(self, batch_id: str, hidden: bool) -> BatchDocument:
        document = self.get_batch(batch_id)
        document.state.hidden = hidden
        document.state.updated_at = now_iso()
        self.save_batch(document)
        self.append_event(batch_id, "batch_hidden" if hidden else "batch_unhidden", {})
        return document

    def delete_batch(self, batch_id: str) -> None:
        batch_dir = self.batch_dir(batch_id)
        self.ensure_batch_dir_is_safe(batch_dir)
        if not batch_dir.exists():
            raise FileNotFoundError(batch_id)
        shutil.rmtree(batch_dir)

    def append_event(self, batch_id: str, event_type: str, payload: dict[str, Any]) -> None:
        batch_dir = self.batch_dir(batch_id)
        batch_dir.mkdir(parents=True, exist_ok=True)
        event = {
            "timestamp": now_iso(),
            "type": event_type,
            "payload": payload,
        }
        with (batch_dir / "events.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def batch_dir(self, batch_id: str) -> Path:
        batch_id = _clean(batch_id)
        if not batch_id or slugify(batch_id) != batch_id:
            raise ValueError("Invalid batch_id.")
        return self.root / batch_id

    def ensure_batch_dir_is_safe(self, batch_dir: Path) -> None:
        root = self.root.resolve()
        target = batch_dir.resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError("Refusing to operate outside the batch root.") from exc

    def _reserve_batch_dir(self, name: str) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        base = slugify(name) or "batch"
        for index in range(1, 1000):
            suffix = "" if index == 1 else f"-{index}"
            batch_dir = self.root / f"{base}{suffix}"
            try:
                batch_dir.mkdir(parents=True, exist_ok=False)
                return batch_dir
            except FileExistsError:
                continue
        raise RuntimeError("Unable to allocate a unique batch directory.")

    @staticmethod
    def _export_item(item: BatchItem) -> dict[str, Any]:
        output_dir = item.output_dir
        song_plan = str(Path(output_dir) / "data" / "song-plan.json") if output_dir else None
        midi = str(Path(output_dir) / "renders" / "song.mid") if output_dir else None
        return {
            "index": item.index,
            "title": item.request.get("title"),
            "status": item.status,
            "job_id": item.job_id,
            "output_dir": item.output_dir,
            "song_plan": song_plan,
            "midi": midi,
            "error": item.error,
        }


def parse_batch_csv(
    csv_text: str,
    *,
    generation_mode: str = "local",
    pipeline_mode: str = "multinode",
) -> list[BatchItem]:
    if not _clean(csv_text):
        raise ValueError("CSV is empty.")

    generation_mode = validate_generation_mode(generation_mode)
    pipeline_mode = validate_pipeline_mode(pipeline_mode)
    reader = csv.DictReader(StringIO(csv_text))
    fieldnames = [field.strip() for field in (reader.fieldnames or []) if field]
    if not fieldnames:
        raise ValueError("CSV is empty.")
    missing = [column for column in REQUIRED_CSV_COLUMNS if column not in fieldnames]
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing)}.")

    items: list[BatchItem] = []
    for index, row in enumerate(reader, start=1):
        row_number = index + 1
        normalized = {str(key).strip(): value for key, value in row.items() if key is not None}
        if not any(_clean(value) for value in normalized.values()):
            continue
        for field_name in REQUIRED_CSV_COLUMNS:
            if not _clean(normalized.get(field_name)):
                raise ValueError(f"CSV row {row_number} is missing required field: {field_name}.")

        row_generation_mode = validate_generation_mode(normalized.get("generation_mode") or generation_mode)
        row_pipeline_mode = validate_pipeline_mode(normalized.get("pipeline_mode") or pipeline_mode)
        request = {
            "title": _clean(normalized.get("title")),
            "language": _clean(normalized.get("language")),
            "style": _clean(normalized.get("style")),
            "theme": _clean(normalized.get("theme")),
            "duration_seconds": _validate_duration(row_number, normalized.get("duration_seconds")),
            "vocal_mode": _clean(normalized.get("vocal_mode")) or "guide_melody",
            "generation_mode": row_generation_mode,
            "pipeline_mode": row_pipeline_mode,
        }
        tempo = _validate_tempo(row_number, normalized.get("tempo_bpm"))
        if tempo is not None:
            request["tempo_bpm"] = tempo
        key = _clean(normalized.get("key"))
        if key:
            request["key"] = key
        lyrics = _clean(normalized.get("lyrics"))
        if lyrics:
            request["lyrics"] = lyrics

        SongRequest.from_dict(request)
        items.append(
            BatchItem(
                item_id=f"item-{index}",
                index=index,
                request=request,
            )
        )

    if not items:
        raise ValueError("CSV has no data rows.")
    return items
