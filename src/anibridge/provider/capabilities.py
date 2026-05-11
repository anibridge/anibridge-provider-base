"""Capability contracts for providers."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence
from datetime import datetime
from typing import cast

from anibridge.provider.base import (
    BrowseableEntry,
    Collection,
    Entry,
    Provider,
    State,
)
from anibridge.provider.types import (
    Key,
    MappingRef,
    ResolvedMapping,
    WebhookPayload,
    WebhookResult,
)

__all__ = [
    "SupportsBackup",
    "SupportsBrowse",
    "SupportsDelete",
    "SupportsDeriveState",
    "SupportsGet",
    "SupportsMappings",
    "SupportsPut",
    "SupportsSearch",
    "SupportsWebhooks",
]


class SupportsBrowse(ABC):
    """Capability for providers that expose browsable collections of entries."""

    @abstractmethod
    async def collections(self) -> Sequence[Collection[Provider]]:
        """Return the top-level collections exposed by the provider."""
        ...

    @abstractmethod
    def entries(
        self,
        collection: Collection[Provider],
        *,
        keys: Sequence[Key] | None = None,
        updated_after: datetime | None = None,
        active_only: bool = False,
    ) -> AsyncIterator[BrowseableEntry[Provider]]:
        """Iterate collection entries with optional filtering."""
        ...


class SupportsWebhooks(ABC):
    """Capability for providers that can parse inbound webhook payloads."""

    @abstractmethod
    def parse_webhook(self, payload: WebhookPayload) -> WebhookResult:
        """Inspect a webhook payload and report whether it applies to the provider."""
        ...


class SupportsMappings(ABC):
    """Capability for providers that resolve cross-provider mapping references."""

    @abstractmethod
    async def resolve_refs(
        self,
        refs: Sequence[MappingRef],
    ) -> Sequence[ResolvedMapping]:
        """Resolve mapping references into provider-native entry keys."""
        ...


class SupportsGet(ABC):
    """Capability for providers that can look up entries by key."""

    @abstractmethod
    async def get(self, key: Key) -> Entry[Provider] | None:
        """Return an entry for a key, or None if absent."""
        ...

    async def get_many(
        self,
        keys: Sequence[Key],
    ) -> Sequence[Entry[Provider] | None]:
        """Fetch multiple entries while preserving input order."""
        provider = cast(Provider, self)
        entries: list[Entry[Provider] | None] = []
        for key in keys:
            try:
                entry = await self.get(key)
            except Exception:
                provider.log.exception("Error fetching entry for key '%s'", key)
                entry = None
            entries.append(entry)
        return entries


class SupportsSearch(ABC):
    """Capability for providers that can search their catalog."""

    @abstractmethod
    async def search(self, query: str) -> Sequence[Entry[Provider]]:
        """Return entries that match the query."""
        ...


class SupportsDeriveState(ABC):
    """Capability for providers that derive state from source context."""

    @abstractmethod
    def derive_state[SourceProviderT: Provider](
        self,
        entries: Sequence[BrowseableEntry[SourceProviderT]],
    ) -> State:
        """Derive a provider-native state update from browseable entries."""
        ...


class SupportsPut(ABC):
    """Capability for providers that can persist derived state."""

    @abstractmethod
    async def put(self, key: Key, state: State) -> Entry[Provider] | None:
        """Persist a provider-native state update for the given key."""
        ...

    async def put_many(
        self,
        updates: Sequence[tuple[Key, State]],
    ) -> Sequence[Entry[Provider] | None]:
        """Process multiple context-derived updates while tolerating failures."""
        provider = cast(Provider, self)
        entries: list[Entry[Provider] | None] = []
        for key, state in updates:
            try:
                entry = await self.put(key, state)
            except Exception:
                provider.log.exception("Error updating entry for key '%s'", key)
                entry = None
            entries.append(entry)
        return entries


class SupportsDelete(ABC):
    """Capability for providers that can delete tracked entries."""

    @abstractmethod
    async def delete(self, key: Key) -> None:
        """Delete the tracked entry associated with the given key."""
        ...


class SupportsBackup(ABC):
    """Capability for providers that can export and restore tracked state."""

    @abstractmethod
    async def export(self) -> str:
        """Export provider state to a serialized backup payload."""
        ...

    @abstractmethod
    async def restore(self, backup: str) -> None:
        """Restore provider state from a serialized backup payload."""
        ...
