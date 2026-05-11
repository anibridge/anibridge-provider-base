"""Public types."""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

__all__ = [
    "Key",
    "Logger",
    "MappingRef",
    "ResolvedMapping",
    "SerializedState",
    "WebhookPayload",
    "WebhookResult",
]


type Key = str
type SerializedState = Mapping[str, str]


@dataclass(frozen=True, slots=True)
class MappingRef:
    """Cross-provider identifier for an entry."""

    provider: str
    id: str
    scope: str | None = None


@dataclass(frozen=True, slots=True)
class ResolvedMapping:
    """Mapping reference resolved into a provider-native entry key."""

    mapping: MappingRef
    key: Key


@dataclass(frozen=True, slots=True)
class WebhookPayload:
    """Framework-agnostic webhook request payload passed to providers."""

    body: bytes = b""
    headers: Mapping[str, str | Sequence[str]] = field(default_factory=dict)
    params: Mapping[str, str | Sequence[str]] = field(default_factory=dict)
    method: str = "POST"
    path: str = ""


@dataclass(frozen=True, slots=True)
class WebhookResult:
    """Result of provider webhook inspection."""

    matched: bool = False
    keys: tuple[Key, ...] = field(default_factory=tuple)


class Logger(logging.Logger):
    """Logger type injected into providers by AniBridge."""

    def success(self, msg: object, *args: object, **kwargs: object) -> None:
        """Success log."""
        ...
