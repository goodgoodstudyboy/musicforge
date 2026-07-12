from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Callable, Literal


NestedZipPolicy = Literal["deny", "allowlisted"]
SemanticVerifier = Callable[[Any], list[dict[str, Any]]]


@dataclass(frozen=True)
class PackageSpec:
    package_type: str
    verification_package_type: str
    check_prefix: str
    required_entries: frozenset[str] = field(default_factory=frozenset)
    optional_entries: frozenset[str] = field(default_factory=frozenset)
    co_required_entry_groups: tuple[frozenset[str], ...] = ()
    allowed_entry_patterns: tuple[str, ...] = ()
    nested_zip_policy: NestedZipPolicy = "deny"
    allowed_nested_entries: frozenset[str] = field(default_factory=frozenset)
    allowed_nested_patterns: tuple[str, ...] = ()
    manifest_entry: str = "manifest.json"
    max_zip_size_mb: int = 128
    max_uncompressed_size_mb: int = 512
    max_entry_count: int = 1000
    redaction_suffixes: tuple[str, ...] = (".json", ".jsonl", ".txt", ".md", ".html")
    semantic_verifier: SemanticVerifier | None = None
    schema_version: int = 1

    @property
    def allowed_entries(self) -> frozenset[str]:
        return self.required_entries | self.optional_entries

    def requiring(self, entries: set[str] | frozenset[str]) -> "PackageSpec":
        required = self.required_entries | frozenset(entries)
        return replace(self, required_entries=required, optional_entries=self.optional_entries - required)
