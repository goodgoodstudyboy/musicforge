# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts.coercion import as_float as _as_float, as_int as _as_int
from song_agent.platform.contracts.documents import DomainDocument
import hashlib as hashlib
import json as json
import re as re
import shutil as shutil
import threading as threading
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from datetime import datetime as datetime, timedelta as timedelta, timezone as timezone
from pathlib import Path as Path
from typing import Mapping as Mapping
from song_agent.domains.creation.edits import SUPPORTED_HARMONY_CHORDS as SUPPORTED_HARMONY_CHORDS
from song_agent.domains.creation.music_quality import attach_quality as attach_quality, analyze_song_quality as analyze_song_quality
from song_agent.domains.studio.projectio import now_iso as now_iso, read_json as read_json, write_json as write_json
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.creation.schemas.song import NoteEvent as NoteEvent, SongPlan as SongPlan, SongSection as SongSection, TrackPlan as TrackPlan

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

EditorPatch = _make_deferred_global('EditorPatch')
EditorPatchError = _make_deferred_global('EditorPatchError')
EditorPatchResult = _make_deferred_global('EditorPatchResult')
_apply_editor_patch_part_01 = _make_deferred_global('_apply_editor_patch_part_01')
_assert_total_bars = _make_deferred_global('_assert_total_bars')
_beats_per_bar = _make_deferred_global('_beats_per_bar')
_bounded_text = _make_deferred_global('_bounded_text')
_choice = _make_deferred_global('_choice')
_chords = _make_deferred_global('_chords')
_clamp = _make_deferred_global('_clamp')
_clean_lyrics = _make_deferred_global('_clean_lyrics')
_delete_note_keys_in_range = _make_deferred_global('_delete_note_keys_in_range')
_delete_selected_notes = _make_deferred_global('_delete_selected_notes')
_float_range = _make_deferred_global('_float_range')
_identity_by_id = _make_deferred_global('_identity_by_id')
_int_range = _make_deferred_global('_int_range')
_map_selected_notes = _make_deferred_global('_map_selected_notes')
_missing_required_track_roles = _make_deferred_global('_missing_required_track_roles')
_note = _make_deferred_global('_note')
_note_identity_by_track_id = _make_deferred_global('_note_identity_by_track_id')
_note_ids = _make_deferred_global('_note_ids')
_note_key = _make_deferred_global('_note_key')
_note_selector = _make_deferred_global('_note_selector')
_optional_after_section_index = _make_deferred_global('_optional_after_section_index')
_remap_note_keys_by_section = _make_deferred_global('_remap_note_keys_by_section')
_round_beat = _make_deferred_global('_round_beat')
_section_from_operation = _make_deferred_global('_section_from_operation')
_section_index_for_plan = _make_deferred_global('_section_index_for_plan')
_section_span = _make_deferred_global('_section_span')
_section_start_beat = _make_deferred_global('_section_start_beat')
_section_start_beat_at_index = _make_deferred_global('_section_start_beat_at_index')
_shift_note_keys_after_beat = _make_deferred_global('_shift_note_keys_after_beat')
_sorted_notes = _make_deferred_global('_sorted_notes')
_total_bars_from_sections = _make_deferred_global('_total_bars_from_sections')
_track_index_for_plan = _make_deferred_global('_track_index_for_plan')
_trim_note_keys_to_total_beats = _make_deferred_global('_trim_note_keys_to_total_beats')
_unique_section_name = _make_deferred_global('_unique_section_name')
_unique_track_name = _make_deferred_global('_unique_track_name')
_update_note = _make_deferred_global('_update_note')
_validate_note_limits = _make_deferred_global('_validate_note_limits')
copy_notes_in_range = _make_deferred_global('copy_notes_in_range')
delete_notes_in_range = _make_deferred_global('delete_notes_in_range')
index = _make_deferred_global('index')
key = _make_deferred_global('key')
normalize_sections = _make_deferred_global('normalize_sections')
remap_notes_by_section = _make_deferred_global('remap_notes_by_section')
shift_notes_after_beat = _make_deferred_global('shift_notes_after_beat')
text = _make_deferred_global('text')
trim_notes_to_total_beats = _make_deferred_global('trim_notes_to_total_beats')

def bind_globals(namespace: dict[str, object]) -> None:
    global EditorPatch, EditorPatchError, EditorPatchResult, _apply_editor_patch_part_01, _assert_total_bars, _beats_per_bar, _bounded_text, _choice
    global _chords, _clamp, _clean_lyrics, _delete_note_keys_in_range, _delete_selected_notes, _float_range, _identity_by_id, _int_range
    global _map_selected_notes, _missing_required_track_roles, _note, _note_identity_by_track_id, _note_ids, _note_key, _note_selector
    global _optional_after_section_index, _remap_note_keys_by_section, _round_beat, _section_from_operation, _section_index_for_plan, _section_span, _section_start_beat, _section_start_beat_at_index
    global _shift_note_keys_after_beat, _sorted_notes, _total_bars_from_sections, _track_index_for_plan, _trim_note_keys_to_total_beats, _unique_section_name, _unique_track_name, _update_note
    global _validate_note_limits, copy_notes_in_range, delete_notes_in_range, index, key, normalize_sections, remap_notes_by_section, shift_notes_after_beat
    global text, trim_notes_to_total_beats
    EditorPatch = namespace.get('EditorPatch', EditorPatch)
    EditorPatchError = namespace.get('EditorPatchError', EditorPatchError)
    EditorPatchResult = namespace.get('EditorPatchResult', EditorPatchResult)
    _apply_editor_patch_part_01 = namespace.get('_apply_editor_patch_part_01', _apply_editor_patch_part_01)
    _assert_total_bars = namespace.get('_assert_total_bars', _assert_total_bars)
    _beats_per_bar = namespace.get('_beats_per_bar', _beats_per_bar)
    _bounded_text = namespace.get('_bounded_text', _bounded_text)
    _choice = namespace.get('_choice', _choice)
    _chords = namespace.get('_chords', _chords)
    _clamp = namespace.get('_clamp', _clamp)
    _clean_lyrics = namespace.get('_clean_lyrics', _clean_lyrics)
    _delete_note_keys_in_range = namespace.get('_delete_note_keys_in_range', _delete_note_keys_in_range)
    _delete_selected_notes = namespace.get('_delete_selected_notes', _delete_selected_notes)
    _float_range = namespace.get('_float_range', _float_range)
    _identity_by_id = namespace.get('_identity_by_id', _identity_by_id)
    _int_range = namespace.get('_int_range', _int_range)
    _map_selected_notes = namespace.get('_map_selected_notes', _map_selected_notes)
    _missing_required_track_roles = namespace.get('_missing_required_track_roles', _missing_required_track_roles)
    _note = namespace.get('_note', _note)
    _note_identity_by_track_id = namespace.get('_note_identity_by_track_id', _note_identity_by_track_id)
    _note_ids = namespace.get('_note_ids', _note_ids)
    _note_key = namespace.get('_note_key', _note_key)
    _note_selector = namespace.get('_note_selector', _note_selector)
    _optional_after_section_index = namespace.get('_optional_after_section_index', _optional_after_section_index)
    _remap_note_keys_by_section = namespace.get('_remap_note_keys_by_section', _remap_note_keys_by_section)
    _round_beat = namespace.get('_round_beat', _round_beat)
    _section_from_operation = namespace.get('_section_from_operation', _section_from_operation)
    _section_index_for_plan = namespace.get('_section_index_for_plan', _section_index_for_plan)
    _section_span = namespace.get('_section_span', _section_span)
    _section_start_beat = namespace.get('_section_start_beat', _section_start_beat)
    _section_start_beat_at_index = namespace.get('_section_start_beat_at_index', _section_start_beat_at_index)
    _shift_note_keys_after_beat = namespace.get('_shift_note_keys_after_beat', _shift_note_keys_after_beat)
    _sorted_notes = namespace.get('_sorted_notes', _sorted_notes)
    _total_bars_from_sections = namespace.get('_total_bars_from_sections', _total_bars_from_sections)
    _track_index_for_plan = namespace.get('_track_index_for_plan', _track_index_for_plan)
    _trim_note_keys_to_total_beats = namespace.get('_trim_note_keys_to_total_beats', _trim_note_keys_to_total_beats)
    _unique_section_name = namespace.get('_unique_section_name', _unique_section_name)
    _unique_track_name = namespace.get('_unique_track_name', _unique_track_name)
    _update_note = namespace.get('_update_note', _update_note)
    _validate_note_limits = namespace.get('_validate_note_limits', _validate_note_limits)
    copy_notes_in_range = namespace.get('copy_notes_in_range', copy_notes_in_range)
    delete_notes_in_range = namespace.get('delete_notes_in_range', delete_notes_in_range)
    index = namespace.get('index', index)
    key = namespace.get('key', key)
    normalize_sections = namespace.get('normalize_sections', normalize_sections)
    remap_notes_by_section = namespace.get('remap_notes_by_section', remap_notes_by_section)
    shift_notes_after_beat = namespace.get('shift_notes_after_beat', shift_notes_after_beat)
    text = namespace.get('text', text)
    trim_notes_to_total_beats = namespace.get('trim_notes_to_total_beats', trim_notes_to_total_beats)
    _bind_deferred_defaults(namespace)


EDITOR_PREVIEW_SCHEMA_VERSION = 1
EDITOR_PATCH_SCHEMA_VERSION = 1
MAX_EDITOR_TRACKS = 32
MAX_EDITOR_NOTES_PER_TRACK = 4096
MAX_EDITOR_OPERATIONS = 200
MAX_NOTE_IDS_PER_OPERATION = 512
MAX_ADDED_NOTES_PER_PATCH = 512
MAX_TOTAL_NOTES_AFTER_PATCH = 16000
MAX_TOTAL_BARS_AFTER_PATCH = 256
MAX_SECTION_BARS = 64
MAX_SECTION_NAME_LENGTH = 40
MAX_TRACK_NAME_LENGTH = 40
MAX_LYRICS_LENGTH = 2000
MAX_INSTRUMENT_LENGTH = 80
NOTE_PATCH_FIELDS = {"pitch", "start_beat", "duration_beats", "velocity"}
SUPPORTED_EDITOR_OPS = {
    "set_section_chords",
    "set_section_lyrics",
    "set_track_instrument",
    "add_section",
    "duplicate_section",
    "delete_section",
    "resize_section",
    "move_section",
    "add_track",
    "duplicate_track",
    "delete_track",
    "rename_track",
    "add_note",
    "update_note",
    "delete_notes",
    "move_notes",
    "transpose_notes",
    "quantize_notes",
    "scale_velocity",
}
QUANTIZE_GRIDS = {0.125, 0.25, 0.5, 1.0}




def _apply_editor_patch_operations_01(parent_plan, operation, op, _split_state) -> bool:
    if op == 'set_section_chords':
        section_index = _section_index_for_plan(operation, _split_state['sections'], _split_state['base_section_names_by_id'])
        chords = _chords(operation.get('chords'))
        _split_state['section'] = _split_state['sections'][section_index]
        _split_state['sections'][section_index] = SongSection(_split_state['section'].name, _split_state['section'].start_bar, _split_state['section'].bars, chords, _split_state['section'].lyrics)
        _split_state['changed_sections'].add(_split_state['section'].name)
        return True
    elif op == 'set_section_lyrics':
        section_index = _section_index_for_plan(operation, _split_state['sections'], _split_state['base_section_names_by_id'])
        lyrics = _clean_lyrics(operation.get('lyrics'))
        _split_state['section'] = _split_state['sections'][section_index]
        _split_state['sections'][section_index] = SongSection(_split_state['section'].name, _split_state['section'].start_bar, _split_state['section'].bars, _split_state['section'].chords, lyrics)
        _split_state['changed_sections'].add(_split_state['section'].name)
        return True
    elif op == 'set_track_instrument':
        track_index = _track_index_for_plan(operation, _split_state['tracks'], _split_state['base_track_names_by_id'])
        instrument = _bounded_text(operation.get('instrument'), MAX_INSTRUMENT_LENGTH)
        if not instrument:
            raise EditorPatchError('instrument must not be empty.')
        _split_state['track'] = _split_state['tracks'][track_index]
        _split_state['tracks'][track_index] = TrackPlan(_split_state['track'].name, instrument, _split_state['track'].notes)
        _split_state['changed_tracks'].add(_split_state['track'].name)
        return True
    elif op == 'add_section':
        beats_per_bar = _beats_per_bar(parent_plan)
        _split_state['section'] = _section_from_operation(operation, _split_state['sections'])
        after_index = _optional_after_section_index(operation, _split_state['sections'], _split_state['base_section_names_by_id'])
        insert_index = len(_split_state['sections']) if after_index is None else after_index + 1
        insert_start = _section_start_beat_at_index(_split_state['sections'], insert_index, beats_per_bar)
        delta = _split_state['section'].bars * beats_per_bar
        _split_state['sections'].insert(insert_index, _split_state['section'])
        _assert_total_bars(_split_state['sections'])
        _split_state['sections'] = normalize_sections(_split_state['sections'])
        _split_state['tracks'] = shift_notes_after_beat(_split_state['tracks'], insert_start, delta)
        _shift_note_keys_after_beat(_split_state['base_note_keys_by_track_id'], insert_start, delta)
        _split_state['total_beats'] = _total_bars_from_sections(_split_state['sections']) * beats_per_bar
        _split_state['changed_sections'].add(_split_state['section'].name)
        _split_state['warnings'].append(f"Section {_split_state['section'].name} was added without notes.")
        return True
    elif op == 'duplicate_section':
        beats_per_bar = _beats_per_bar(parent_plan)
        source_index = _section_index_for_plan(operation, _split_state['sections'], _split_state['base_section_names_by_id'])
        source = _split_state['sections'][source_index]
        new_name = _unique_section_name(operation.get('name'), _split_state['sections'])
        after_index = _optional_after_section_index(operation, _split_state['sections'], _split_state['base_section_names_by_id'])
        insert_index = len(_split_state['sections']) if after_index is None else after_index + 1
        source_start = _section_start_beat(source, beats_per_bar)
        source_end = source_start + source.bars * beats_per_bar
        insert_start = _section_start_beat_at_index(_split_state['sections'], insert_index, beats_per_bar)
        delta = source.bars * beats_per_bar
        new_section = SongSection(new_name, 1, source.bars, list(source.chords), source.lyrics)
        _split_state['tracks'] = shift_notes_after_beat(_split_state['tracks'], insert_start, delta)
        _shift_note_keys_after_beat(_split_state['base_note_keys_by_track_id'], insert_start, delta)
        if bool(operation.get('copy_notes', True)):
            shifted_source_start = source_start + (delta if insert_start <= source_start else 0)
            shifted_source_end = source_end + (delta if insert_start <= source_start else 0)
            _split_state['tracks'] = copy_notes_in_range(_split_state['tracks'], shifted_source_start, shifted_source_end, insert_start)
        _split_state['sections'].insert(insert_index, new_section)
        _assert_total_bars(_split_state['sections'])
        _split_state['sections'] = normalize_sections(_split_state['sections'])
        _split_state['total_beats'] = _total_bars_from_sections(_split_state['sections']) * beats_per_bar
        _split_state['changed_sections'].update({source.name, new_name})
        for _split_state['track'] in _split_state['tracks']:
            if any((insert_start <= note.start_beat < insert_start + delta for note in _split_state['track'].notes)):
                _split_state['changed_tracks'].add(_split_state['track'].name)
        return True
    elif op == 'delete_section':
        beats_per_bar = _beats_per_bar(parent_plan)
        if len(_split_state['sections']) <= 1:
            raise EditorPatchError('Cannot delete the last section.')
        section_index = _section_index_for_plan(operation, _split_state['sections'], _split_state['base_section_names_by_id'])
        _split_state['section'] = _split_state['sections'][section_index]
        policy = _choice(operation.get('note_policy') or 'delete', 'note_policy', {'delete', 'shift_left', 'keep_absolute'})
        start = _section_start_beat(_split_state['section'], beats_per_bar)
        end = start + _split_state['section'].bars * beats_per_bar
        delta = -(_split_state['section'].bars * beats_per_bar)
        if policy in {'delete', 'shift_left'}:
            _split_state['tracks'] = delete_notes_in_range(_split_state['tracks'], start, end)
            _delete_note_keys_in_range(_split_state['base_note_keys_by_track_id'], start, end)
            _split_state['tracks'] = shift_notes_after_beat(_split_state['tracks'], end, delta)
            _shift_note_keys_after_beat(_split_state['base_note_keys_by_track_id'], end, delta)
        _split_state['sections'].pop(section_index)
        _split_state['base_section_names_by_id'][str(operation.get('section_id') or '')] = None
        _split_state['sections'] = normalize_sections(_split_state['sections'])
        _split_state['total_beats'] = _total_bars_from_sections(_split_state['sections']) * beats_per_bar
        if policy == 'keep_absolute':
            _split_state['tracks'] = trim_notes_to_total_beats(_split_state['tracks'], _split_state['total_beats'], _split_state['warnings'])
            _trim_note_keys_to_total_beats(_split_state['base_note_keys_by_track_id'], _split_state['total_beats'])
        _split_state['changed_sections'].add(_split_state['section'].name)
        _split_state['changed_tracks'].update((_split_state['track'].name for _split_state['track'] in _split_state['tracks']))
        return True
    elif op == 'resize_section':
        beats_per_bar = _beats_per_bar(parent_plan)
        section_index = _section_index_for_plan(operation, _split_state['sections'], _split_state['base_section_names_by_id'])
        _split_state['section'] = _split_state['sections'][section_index]
        new_bars = _int_range(operation.get('bars'), 'bars', 1, MAX_SECTION_BARS)
        policy = _choice(operation.get('note_policy') or 'shift_tail', 'note_policy', {'shift_tail', 'crop'})
        old_bars = _split_state['section'].bars
        if new_bars == old_bars:
            _split_state['changed_sections'].add(_split_state['section'].name)
        else:
            old_end = _section_start_beat(_split_state['section'], beats_per_bar) + old_bars * beats_per_bar
            new_end = _section_start_beat(_split_state['section'], beats_per_bar) + new_bars * beats_per_bar
            delta = (new_bars - old_bars) * beats_per_bar
            if delta < 0 and policy == 'crop':
                _split_state['tracks'] = delete_notes_in_range(_split_state['tracks'], new_end, old_end)
                _delete_note_keys_in_range(_split_state['base_note_keys_by_track_id'], new_end, old_end)
            _split_state['tracks'] = shift_notes_after_beat(_split_state['tracks'], old_end, delta)
            _shift_note_keys_after_beat(_split_state['base_note_keys_by_track_id'], old_end, delta)
            _split_state['sections'][section_index] = SongSection(_split_state['section'].name, _split_state['section'].start_bar, new_bars, list(_split_state['section'].chords), _split_state['section'].lyrics)
            _assert_total_bars(_split_state['sections'])
            _split_state['sections'] = normalize_sections(_split_state['sections'])
            _split_state['total_beats'] = _total_bars_from_sections(_split_state['sections']) * beats_per_bar
            _split_state['tracks'] = trim_notes_to_total_beats(_split_state['tracks'], _split_state['total_beats'], _split_state['warnings'])
            _trim_note_keys_to_total_beats(_split_state['base_note_keys_by_track_id'], _split_state['total_beats'])
            _split_state['changed_sections'].add(_split_state['section'].name)
            _split_state['changed_tracks'].update((_split_state['track'].name for _split_state['track'] in _split_state['tracks']))
        return True
    elif op == 'move_section':
        beats_per_bar = _beats_per_bar(parent_plan)
        section_index = _section_index_for_plan(operation, _split_state['sections'], _split_state['base_section_names_by_id'])
        after_index = _optional_after_section_index(operation, _split_state['sections'], _split_state['base_section_names_by_id'], allow_self=False)
        _split_state['section'] = _split_state['sections'][section_index]
        before_names = [item.name for item in _split_state['sections']]
        old_spans_by_name = {item.name: _section_span(item, beats_per_bar) for item in _split_state['sections']}
        moved = _split_state['sections'].pop(section_index)
        if after_index is None:
            insert_index = 0
        else:
            insert_index = after_index + 1
            if after_index > section_index:
                insert_index -= 1
        _split_state['sections'].insert(insert_index, moved)
        if [item.name for item in _split_state['sections']] == before_names:
            _split_state['changed_sections'].add(_split_state['section'].name)
        else:
            _split_state['sections'] = normalize_sections(_split_state['sections'])
            new_spans_by_name = {item.name: _section_span(item, beats_per_bar) for item in _split_state['sections']}
            move_names = set(before_names) if bool(operation.get('move_notes', True)) else set(before_names) - {_split_state['section'].name}
            _split_state['tracks'] = remap_notes_by_section(_split_state['tracks'], old_spans_by_name, new_spans_by_name, move_names=move_names)
            _remap_note_keys_by_section(_split_state['base_note_keys_by_track_id'], old_spans_by_name, new_spans_by_name, move_names=move_names)
            _split_state['total_beats'] = _total_bars_from_sections(_split_state['sections']) * beats_per_bar
            _split_state['changed_sections'].add(_split_state['section'].name)
            _split_state['changed_tracks'].update((_split_state['track'].name for _split_state['track'] in _split_state['tracks']))
        return True
    elif op == 'add_track':
        if len(_split_state['tracks']) >= MAX_EDITOR_TRACKS:
            raise EditorPatchError(f'editor supports at most {MAX_EDITOR_TRACKS} tracks.')
        name = _unique_track_name(operation.get('name'), _split_state['tracks'])
        instrument = _bounded_text(operation.get('instrument'), MAX_INSTRUMENT_LENGTH)
        if not instrument:
            raise EditorPatchError('instrument must not be empty.')
        _split_state['tracks'].append(TrackPlan(name, instrument, []))
        _split_state['changed_tracks'].add(name)
        _split_state['warnings'].append(f'Track {name} was added without notes.')
        return True
    else:
        return False

def _apply_editor_patch_operations_02(parent_plan, operation, op, _split_state) -> bool:
    if op == 'duplicate_track':
        if len(_split_state['tracks']) >= MAX_EDITOR_TRACKS:
            raise EditorPatchError(f'editor supports at most {MAX_EDITOR_TRACKS} tracks.')
        track_index = _track_index_for_plan(operation, _split_state['tracks'], _split_state['base_track_names_by_id'])
        source = _split_state['tracks'][track_index]
        name = _unique_track_name(operation.get('name'), _split_state['tracks'])
        instrument = _bounded_text(operation.get('instrument') or source.instrument, MAX_INSTRUMENT_LENGTH)
        transpose = _int_range(operation.get('transpose', 0), 'transpose', -24, 24)
        notes = [NoteEvent(_clamp(note.pitch + transpose, 0, 127), note.start_beat, note.duration_beats, note.velocity) for note in source.notes]
        _split_state['tracks'].append(TrackPlan(name, instrument, _sorted_notes(notes)))
        _split_state['changed_tracks'].update({source.name, name})
        return True
    elif op == 'delete_track':
        if len(_split_state['tracks']) <= 1:
            raise EditorPatchError('Cannot delete the last track.')
        track_index = _track_index_for_plan(operation, _split_state['tracks'], _split_state['base_track_names_by_id'])
        _split_state['track'] = _split_state['tracks'][track_index]
        remaining = [item for index, item in enumerate(_split_state['tracks']) if index != track_index]
        if _split_state['track'].notes and (not any((item.notes for item in remaining))) and (not bool(operation.get('allow_empty_song'))):
            raise EditorPatchError('Cannot delete the last track with notes unless allow_empty_song is true.')
        if _split_state['track'].notes and (not any((item.notes for item in remaining))):
            _split_state['warnings'].append('All notes were removed by deleting the last non-empty track.')
        if _missing_required_track_roles(remaining) and (not bool(operation.get('allow_empty_song'))):
            raise EditorPatchError('Cannot delete required track roles unless allow_empty_song is true.')
        _split_state['tracks'] = remaining
        _split_state['base_track_names_by_id'][str(operation.get('track_id') or '')] = None
        _split_state['changed_tracks'].add(_split_state['track'].name)
        return True
    elif op == 'rename_track':
        track_index = _track_index_for_plan(operation, _split_state['tracks'], _split_state['base_track_names_by_id'])
        _split_state['track'] = _split_state['tracks'][track_index]
        name = _unique_track_name(operation.get('name'), [item for index, item in enumerate(_split_state['tracks']) if index != track_index])
        _split_state['tracks'][track_index] = TrackPlan(name, _split_state['track'].instrument, _split_state['track'].notes)
        _split_state['base_track_names_by_id'][str(operation.get('track_id') or '')] = name
        _split_state['changed_tracks'].update({_split_state['track'].name, name})
        return True
    elif op == 'add_note':
        track_index = _track_index_for_plan(operation, _split_state['tracks'], _split_state['base_track_names_by_id'])
        if _split_state['added_notes'] >= MAX_ADDED_NOTES_PER_PATCH:
            raise EditorPatchError(f'editor patch can add at most {MAX_ADDED_NOTES_PER_PATCH} notes.')
        note = _note(operation.get('note'), _split_state['total_beats'])
        _split_state['track'] = _split_state['tracks'][track_index]
        _split_state['tracks'][track_index] = TrackPlan(_split_state['track'].name, _split_state['track'].instrument, _sorted_notes([*_split_state['track'].notes, note]))
        _split_state['changed_tracks'].add(_split_state['track'].name)
        _split_state['added_notes'] += 1
        return True
    elif op == 'update_note':
        track_index = _track_index_for_plan(operation, _split_state['tracks'], _split_state['base_track_names_by_id'])
        _split_state['track'] = _split_state['tracks'][track_index]
        note_keys_by_id = _split_state['base_note_keys_by_track_id'].get(str(operation.get('track_id') or ''), {})
        notes, updated_note = _update_note(_split_state['track'], note_keys_by_id, operation, _split_state['total_beats'])
        note_keys_by_id[str(operation.get('note_id') or '')] = _note_key(updated_note)
        _split_state['tracks'][track_index] = TrackPlan(_split_state['track'].name, _split_state['track'].instrument, notes)
        _split_state['changed_tracks'].add(_split_state['track'].name)
        return True
    elif op == 'delete_notes':
        track_index = _track_index_for_plan(operation, _split_state['tracks'], _split_state['base_track_names_by_id'])
        _split_state['track'] = _split_state['tracks'][track_index]
        selected = set(_note_ids(operation.get('note_ids')))
        note_keys_by_id = _split_state['base_note_keys_by_track_id'].get(str(operation.get('track_id') or ''), {})
        notes, deleted_note_ids = _delete_selected_notes(_split_state['track'], note_keys_by_id, selected)
        for note_id in deleted_note_ids:
            note_keys_by_id[note_id] = None
        if not notes:
            _split_state['warnings'].append(f"Track {_split_state['track'].name} has no notes after editor patch.")
        _split_state['tracks'][track_index] = TrackPlan(_split_state['track'].name, _split_state['track'].instrument, notes)
        _split_state['changed_tracks'].add(_split_state['track'].name)
        return True
    elif op == 'move_notes':
        track_index = _track_index_for_plan(operation, _split_state['tracks'], _split_state['base_track_names_by_id'])
        delta = _float_range(operation.get('delta_beats'), 'delta_beats', -64.0, 64.0)
        _split_state['track'] = _split_state['tracks'][track_index]
        ids = set(_note_ids(operation.get('note_ids')))
        note_keys_by_id = _split_state['base_note_keys_by_track_id'].get(str(operation.get('track_id') or ''), {})
        notes, updated_keys = _map_selected_notes(_split_state['track'], note_keys_by_id=note_keys_by_id, ids=ids, total_beats=_split_state['total_beats'], mapper=lambda note: NoteEvent(note.pitch, _round_beat(note.start_beat + delta), note.duration_beats, note.velocity))
        note_keys_by_id.update(updated_keys)
        _split_state['tracks'][track_index] = TrackPlan(_split_state['track'].name, _split_state['track'].instrument, notes)
        _split_state['changed_tracks'].add(_split_state['track'].name)
        return True
    elif op == 'transpose_notes':
        track_index = _track_index_for_plan(operation, _split_state['tracks'], _split_state['base_track_names_by_id'])
        semitones = _int_range(operation.get('semitones'), 'semitones', -24, 24)
        _split_state['track'] = _split_state['tracks'][track_index]
        selector = _note_selector(operation, _split_state['track'])
        note_keys_by_id = _split_state['base_note_keys_by_track_id'].get(str(operation.get('track_id') or ''), {})
        notes, updated_keys = _map_selected_notes(_split_state['track'], note_keys_by_id=note_keys_by_id, ids=selector.get('ids'), beat_range=selector.get('range'), total_beats=_split_state['total_beats'], mapper=lambda note: NoteEvent(_clamp(note.pitch + semitones, 0, 127), note.start_beat, note.duration_beats, note.velocity))
        note_keys_by_id.update(updated_keys)
        _split_state['tracks'][track_index] = TrackPlan(_split_state['track'].name, _split_state['track'].instrument, notes)
        _split_state['changed_tracks'].add(_split_state['track'].name)
        return True
    elif op == 'quantize_notes':
        track_index = _track_index_for_plan(operation, _split_state['tracks'], _split_state['base_track_names_by_id'])
        grid = float(operation.get('grid'))
        if grid not in QUANTIZE_GRIDS:
            raise EditorPatchError('grid must be one of 0.125, 0.25, 0.5, 1.0.')
        _split_state['track'] = _split_state['tracks'][track_index]
        selector = _note_selector(operation, _split_state['track'])
        note_keys_by_id = _split_state['base_note_keys_by_track_id'].get(str(operation.get('track_id') or ''), {})
        notes, updated_keys = _map_selected_notes(_split_state['track'], note_keys_by_id=note_keys_by_id, ids=selector.get('ids'), beat_range=selector.get('range'), total_beats=_split_state['total_beats'], mapper=lambda note: NoteEvent(note.pitch, _round_beat(round(note.start_beat / grid) * grid), note.duration_beats, note.velocity))
        note_keys_by_id.update(updated_keys)
        _split_state['tracks'][track_index] = TrackPlan(_split_state['track'].name, _split_state['track'].instrument, notes)
        _split_state['changed_tracks'].add(_split_state['track'].name)
        return True
    elif op == 'scale_velocity':
        track_index = _track_index_for_plan(operation, _split_state['tracks'], _split_state['base_track_names_by_id'])
        factor = _float_range(operation.get('factor'), 'factor', 0.25, 2.0)
        _split_state['track'] = _split_state['tracks'][track_index]
        selector = _note_selector(operation, _split_state['track'])
        note_keys_by_id = _split_state['base_note_keys_by_track_id'].get(str(operation.get('track_id') or ''), {})
        notes, updated_keys = _map_selected_notes(_split_state['track'], note_keys_by_id=note_keys_by_id, ids=selector.get('ids'), beat_range=selector.get('range'), total_beats=_split_state['total_beats'], mapper=lambda note: NoteEvent(note.pitch, note.start_beat, note.duration_beats, _clamp(round(note.velocity * factor), 1, 127)))
        note_keys_by_id.update(updated_keys)
        _split_state['tracks'][track_index] = TrackPlan(_split_state['track'].name, _split_state['track'].instrument, notes)
        _split_state['changed_tracks'].add(_split_state['track'].name)
        return True
    else:
        return False

def _apply_editor_patch_part_02(parent_plan: SongPlan, patch_data: DomainDocument | EditorPatch, _split_state):
    for operation in _split_state['patch'].operations:
        op = str(operation.get('op') or '')
        _split_state['summary_counts'][op] = _split_state['summary_counts'].get(op, 0) + 1
        if _apply_editor_patch_operations_01(parent_plan, operation, op, _split_state):
            continue
        if _apply_editor_patch_operations_02(parent_plan, operation, op, _split_state):
            continue
    return (False, None)

def _apply_editor_patch_part_03(parent_plan: SongPlan, patch_data: DomainDocument | EditorPatch, _split_state):
    _validate_note_limits(_split_state['tracks'])
    edited = SongPlan(title=parent_plan.title, key=parent_plan.key, tempo_bpm=parent_plan.tempo_bpm, meter=parent_plan.meter, sections=_split_state['sections'], tracks=[TrackPlan(_split_state['track'].name, _split_state['track'].instrument, _sorted_notes(_split_state['track'].notes)) for _split_state['track'] in _split_state['tracks']], quality=parent_plan.quality)
    edited = attach_quality(edited)
    edited.validate()
    summary = {'operation_counts': _split_state['summary_counts'], 'changed_sections': sorted(_split_state['changed_sections']), 'changed_tracks': sorted(_split_state['changed_tracks']), 'section_identity': _identity_by_id(_split_state['base_section_names_by_id']), 'track_identity': _identity_by_id(_split_state['base_track_names_by_id']), 'note_identity': _note_identity_by_track_id(_split_state['base_note_keys_by_track_id'])}
    return (True, EditorPatchResult(plan=edited, patch=_split_state['patch'], summary=summary, warnings=_split_state['warnings']))
    return (False, None)

def apply_editor_patch(parent_plan: SongPlan, patch_data: DomainDocument | EditorPatch) -> EditorPatchResult:
    _split_state: DomainDocument = {}
    _split_result = _apply_editor_patch_part_01(parent_plan, patch_data, _split_state)
    if _split_result[0]:
        return _split_result[1]
    _split_result = _apply_editor_patch_part_02(parent_plan, patch_data, _split_state)
    if _split_result[0]:
        return _split_result[1]
    _split_result = _apply_editor_patch_part_03(parent_plan, patch_data, _split_state)
    if _split_result[0]:
        return _split_result[1]
    raise RuntimeError("apply_editor_patch did not produce a result.")

def summarize_editor_patch(result: EditorPatchResult) -> DomainDocument:
    return {
        "operation_count": len(result.patch.operations),
        "changed_sections": list(result.summary.get("changed_sections") or []),
        "changed_tracks": list(result.summary.get("changed_tracks") or []),
        "operation_counts": dict(result.summary.get("operation_counts") or {}),
        "warnings": list(result.warnings),
    }

def describe_editor_operations(operations: list[DomainDocument]) -> list[str]:
    descriptions = []
    for operation in operations:
        op = str(operation.get("op") or "")
        if op == "add_section":
            descriptions.append(f"add_section: {_operation_name(operation, 'name', 'section')} after {operation.get('after_section_id') or 'end'}")
        elif op == "duplicate_section":
            descriptions.append(f"duplicate_section: {operation.get('section_id') or '?'} -> {_operation_name(operation, 'name', 'copy')}")
        elif op == "delete_section":
            descriptions.append(f"delete_section: {operation.get('section_id') or '?'}")
        elif op == "resize_section":
            descriptions.append(f"resize_section: {operation.get('section_id') or '?'} -> {operation.get('bars')} bars")
        elif op == "move_section":
            descriptions.append(f"move_section: {operation.get('section_id') or '?'} after {operation.get('after_section_id') or 'start'}")
        elif op == "add_track":
            descriptions.append(f"add_track: {_operation_name(operation, 'name', 'track')}")
        elif op == "duplicate_track":
            descriptions.append(f"duplicate_track: {operation.get('track_id') or '?'} -> {_operation_name(operation, 'name', 'copy')}")
        elif op == "delete_track":
            descriptions.append(f"delete_track: {operation.get('track_id') or '?'}")
        elif op == "rename_track":
            descriptions.append(f"rename_track: {operation.get('track_id') or '?'} -> {_operation_name(operation, 'name', 'track')}")
        elif op == "set_section_chords":
            descriptions.append(f"set_section_chords: {operation.get('section_id') or '?'}")
        elif op == "set_section_lyrics":
            descriptions.append(f"set_section_lyrics: {operation.get('section_id') or '?'}")
        elif op == "set_track_instrument":
            descriptions.append(f"set_track_instrument: {operation.get('track_id') or '?'}")
        elif op in {"add_note", "update_note", "delete_notes", "move_notes", "transpose_notes", "quantize_notes", "scale_velocity"}:
            descriptions.append(f"{op}: {operation.get('track_id') or '?'}")
        else:
            descriptions.append(op or "unknown_operation")
    return descriptions

def _operation_counts(operations: list[DomainDocument]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for operation in operations:
        op = str(operation.get("op") or "unknown_operation")
        counts[op] = counts.get(op, 0) + 1
    return counts

def _operation_name(operation: DomainDocument, field_name: str, fallback: str) -> str:
    value = sanitize_sensitive_text(str(operation.get(field_name) or "")).strip()
    return value[:80] if value else fallback

def _patch_metadata(value: object) -> DomainDocument:
    if not isinstance(value, dict):
        return {}
    metadata = sanitize_metadata(dict(value))
    raw = json.dumps(metadata, ensure_ascii=False)
    if len(raw.encode("utf-8")) > 32_000:
        raise EditorPatchError("editor patch metadata must be 32000 bytes or fewer.")
    return metadata

def _clip_inserts_from_metadata(metadata: DomainDocument) -> list[DomainDocument]:
    inserts = metadata.get("clip_inserts") if isinstance(metadata, dict) else None
    if not isinstance(inserts, list):
        return []
    cleaned = []
    for item in inserts[:20]:
        if isinstance(item, dict):
            cleaned.append(sanitize_metadata(dict(item)))
    return cleaned

def _template_inserts_from_metadata(metadata: DomainDocument) -> list[DomainDocument]:
    inserts = metadata.get("template_inserts") if isinstance(metadata, dict) else None
    if not isinstance(inserts, list):
        return []
    cleaned = []
    for item in inserts[:20]:
        if isinstance(item, dict):
            cleaned.append(sanitize_metadata(dict(item)))
    return cleaned

def _structure_edit_summary(operations: list[DomainDocument]) -> DomainDocument:
    section_ops = {"add_section", "duplicate_section", "delete_section", "resize_section", "move_section"}
    track_ops = {"add_track", "duplicate_track", "delete_track", "rename_track"}
    counts = _operation_counts([operation for operation in operations if str(operation.get("op") or "") in section_ops | track_ops])
    if not counts:
        return {}
    return {
        "section_operations": {key: value for key, value in counts.items() if key in section_ops},
        "track_operations": {key: value for key, value in counts.items() if key in track_ops},
        "operation_text": [
            text
            for operation, text in zip(operations, describe_editor_operations(operations))
            if str(operation.get("op") or "") in section_ops | track_ops
        ],
    }
