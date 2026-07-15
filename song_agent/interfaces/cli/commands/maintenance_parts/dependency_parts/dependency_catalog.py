from __future__ import annotations

import argparse

import json

import sys

import os

from pathlib import Path

from typing import Any

from song_agent.application.generation.service import generate_request

from song_agent.application.legacy_dependencies.auth import build_auth_config

from song_agent.application.legacy_dependencies.projectio import read_json, write_json

from song_agent.application.legacy_dependencies.provider import (
    ProviderConfig,
    ProviderError,
    load_provider_config,
    provider_configured,
    test_provider_config,
)

from song_agent.application.legacy_dependencies.schemas__song import SongRequest

from song_agent.application.interface_persistence import write_interface_document

from song_agent.interfaces.cli.registry import CommandSpec


from song_agent.application.legacy_dependencies.lts_maintenance import LTSMaintenanceStore, MAINTENANCE_PROFILES

from song_agent.application.legacy_dependencies.lts_backup_verifier import (
    maintenance_backup_verification_exit_code,
    print_maintenance_backup_verification_report,
    verify_maintenance_backup_zip,
    write_maintenance_backup_verification_report,
)

__all__ = ['Any', 'CommandSpec', 'LTSMaintenanceStore', 'MAINTENANCE_PROFILES', 'Path', 'ProviderConfig', 'ProviderError', 'SongRequest', 'argparse', 'build_auth_config', 'generate_request', 'json', 'load_provider_config', 'maintenance_backup_verification_exit_code', 'os', 'print_maintenance_backup_verification_report', 'provider_configured', 'read_json', 'sys', 'test_provider_config', 'verify_maintenance_backup_zip', 'write_interface_document', 'write_json', 'write_maintenance_backup_verification_report']
