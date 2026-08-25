"""Scope model and intersection algebra — the heart of the compiler.

Semantics (CONTEXT.md D5, invariant 1):
- Intersection ONLY narrows: channels ∩, territories ∩, until=min, exclusions ∪.
- An empty dimension anywhere collapses the whole scope (never widens).
- Adding a claim to a set of claims can never enlarge the resulting scope.

Property tests live in tests/test_scope_properties.py.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass, field


def _freeze(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


@dataclass(frozen=True)
class Scope:
    """A permission scope. All dimensions intersect; any empty dimension = empty scope."""

    channels: frozenset[str] = field(default_factory=frozenset)
    territories: frozenset[str] = field(default_factory=frozenset)
    valid_until: dt.datetime | None = None
    exclusions: frozenset[str] = field(default_factory=frozenset)
    unlimited: bool = False   # True only for a wildcard root; still narrowed by intersects

    def is_empty(self) -> bool:
        if self.unlimited:
            return False
        return not (self.channels and self.territories)

    def __bool__(self) -> bool:  # truthiness == non-empty
        return not self.is_empty()

    def union(self, other: "Scope") -> "Scope":
        """Merge alternative grants FROM THE SAME SOURCE (same asset+claim kind).
        Licenses are OR-ed: channels ∪, territories ∪, until = max, exclusions ∪
        (constraints always accumulate — fail-closed). Never applied across sources;
        cross-source combination goes through intersect()."""
        until = self.valid_until
        if other.valid_until is not None:
            until = other.valid_until if until is None else max(until, other.valid_until)
        return Scope(
            channels=self.channels | other.channels,
            territories=self.territories | other.territories,
            valid_until=until,
            exclusions=self.exclusions | other.exclusions,
            unlimited=self.unlimited or other.unlimited,
        )

    def _narrow(self, other: "Scope") -> "Scope":
        if other.unlimited:
            return self
        if self.unlimited:
            return other
        channels = self.channels & other.channels
        territories = self.territories & other.territories
        exclusions = self.exclusions | other.exclusions
        until = self.valid_until
        if other.valid_until is not None:
            until = other.valid_until if until is None else min(until, other.valid_until)
        return Scope(channels=channels, territories=territories,
                     valid_until=until, exclusions=exclusions)

    def intersect(self, *others: "Scope") -> "Scope":
        result = self
        for other in others:
            result = result._narrow(other)
            if result.is_empty():
                # keep collapsing deterministically to the canonical empty scope
                return EMPTY_SCOPE
        return result

    def covers(self, channel: str | None = None, territory: str | None = None,
               now: dt.datetime | None = None) -> tuple[bool, str]:
        """Coverage check used by the gate. Returns (ok, failure_detail)."""
        if self.is_empty():
            return False, "scope is empty"
        if channel is not None and self.channels and channel not in self.channels:
            return False, f"channel '{channel}' outside {sorted(self.channels)}"
        if territory is not None and self.territories and territory not in self.territories:
            return False, f"territory '{territory}' outside {sorted(self.territories)}"
        if now is not None and self.valid_until is not None and now >= self.valid_until:
            return False, f"window expired at {self.valid_until.isoformat()}"
        return True, ""

    def fingerprint(self) -> str:
        if self.is_empty():
            payload = '"EMPTY"'
        else:
            payload = json.dumps({
                "channels": sorted(self.channels),
                "territories": sorted(self.territories),
                "valid_until": self.valid_until.isoformat() if self.valid_until else None,
                "exclusions": sorted(self.exclusions),
                "unlimited": self.unlimited,
            }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


EMPTY_SCOPE = Scope()


def wildcard_scope() -> Scope:
    """Root scope for fully-owned original assets: covers everything until narrowed."""
    return Scope(unlimited=True)
