from __future__ import annotations
import argparse
import json
import sys
import os
from pathlib import Path
from song_agent.application.generation.service import generate_request
from song_agent.platform.auth import build_auth_config
from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.creation.provider import ProviderConfig, ProviderError, load_provider_config, provider_configured, test_provider_config
from song_agent.domains.creation.schemas.song import SongRequest
from song_agent.application.interface_persistence import write_interface_document
from song_agent.interfaces.cli.registry import CommandSpec
from song_agent.release_check.matrix import release_check_profiles
from song_agent.domains.trust.ga_readiness import build_ga_readiness_report, write_ga_readiness_report
from song_agent.release_check.runner import run_release_check_matrix
from song_agent.domains.trust.ga_readiness_verifier import verify_ga_readiness_report, write_ga_readiness_verification_report
from song_agent.release_check.matrix import release_check_definitions_as_dicts, select_check_definitions
from song_agent.release_check.runner import print_release_check_report, write_json_report, write_timing_report

__all__ = ['CommandSpec', 'Path', 'ProviderConfig', 'ProviderError', 'SongRequest', 'argparse', 'build_auth_config', 'build_ga_readiness_report', 'generate_request', 'json', 'load_provider_config', 'os', 'print_release_check_report', 'provider_configured', 'read_json', 'release_check_definitions_as_dicts', 'release_check_profiles', 'run_release_check_matrix', 'select_check_definitions', 'sys', 'test_provider_config', 'verify_ga_readiness_report', 'write_ga_readiness_report', 'write_ga_readiness_verification_report', 'write_interface_document', 'write_json', 'write_json_report', 'write_timing_report']
