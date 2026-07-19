# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document

import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import threading as threading
import zipfile as zipfile
from datetime import datetime as datetime, timedelta as timedelta, timezone as timezone
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.version import VERSION as __version__
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.trust.public_trust_center_publication_monitoring import verification_hash as verification_hash
from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS as DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.trust.trust_operations_continuous_assurance import TrustOperationsAssuranceStore as TrustOperationsAssuranceStore
from song_agent.domains.trust.trust_operations_hub import TrustOperationsHubStore as TrustOperationsHubStore
from song_agent.domains.trust.trust_operations_assurance_watch_contracts import ASSURANCE_WATCH_ARCHIVE_ENTRIES as ASSURANCE_WATCH_ARCHIVE_ENTRIES, TRUST_OPERATIONS_ASSURANCE_WATCH_ACTION_PACK_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_ACTION_PACK_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_BLOCKED_KEYS as TRUST_OPERATIONS_ASSURANCE_WATCH_BLOCKED_KEYS, TRUST_OPERATIONS_ASSURANCE_WATCH_EXTERNAL_SUMMARY_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_EXTERNAL_SUMMARY_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_HASH_EXCLUDE_KEYS as TRUST_OPERATIONS_ASSURANCE_WATCH_HASH_EXCLUDE_KEYS, TRUST_OPERATIONS_ASSURANCE_WATCH_MANIFEST_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_MANIFEST_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_QUEUE_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_QUEUE_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_RUN_INDEX_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_RUN_INDEX_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEDULE_PACKAGE_TYPE as TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEDULE_PACKAGE_TYPE, TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEMA_VERSION as TRUST_OPERATIONS_ASSURANCE_WATCH_SCHEMA_VERSION, watch_hash as watch_hash, watch_manifest_hash as watch_manifest_hash















class TrustOperationsAssuranceWatchError(ValueError):
    pass


class TrustOperationsAssuranceWatchNotFoundError(TrustOperationsAssuranceWatchError):
    pass


class TrustOperationsAssuranceWatchStateError(TrustOperationsAssuranceWatchError):
    pass


from song_agent.domains.trust import v142_toaw_readiness as _v142_toaw_readiness
from song_agent.domains.trust.v142_toaw_readiness import TrustOperationsAssuranceWatchStore as TrustOperationsAssuranceWatchStore
from song_agent.domains.trust import v142_toaw_evidence as _v142_toaw_evidence
from song_agent.domains.trust.v142_toaw_evidence import _default_schedule as _default_schedule, _external_row as _external_row, _public_row as _public_row, _action as _action, _actions_for_row as _actions_for_row, _queue_summary as _queue_summary, _queue_status as _queue_status, _action_summary as _action_summary, _manifest as _manifest, _manifest_files as _manifest_files, _due_status as _due_status, _parse_dt as _parse_dt, _latest_run as _latest_run, _source_paths as _source_paths, _verifier_kwargs_from_source_paths as _verifier_kwargs_from_source_paths, _paths as _paths, _first_path as _first_path, _list as _list, _read_json_required as _read_json_required, _read_json_default as _read_json_default, _read_zip_json_optional as _read_zip_json_optional, _write_json as _write_json, _write_internal_json as _write_internal_json, _append_jsonl as _append_jsonl, _read_text as _read_text, _write_readme as _write_readme, _zip_entries as _zip_entries, _write_zip as _write_zip, _sha256 as _sha256, _next_id as _next_id, _safe_id as _safe_id, _deep_update as _deep_update, _clone as _clone, _mkdir as _mkdir, _fs_path as _fs_path, _now as _now, _sanitize as _sanitize, _sanitize_text as _sanitize_text

_v142_toaw_readiness.bind_globals(globals())
_v142_toaw_evidence.bind_globals(globals())
