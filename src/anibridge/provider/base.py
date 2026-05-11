"""Provider base contracts."""

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import ClassVar, Self, cast

from anibridge.provider.types import Key, Logger, MappingRef, SerializedState

__all__ = [
    "Activity",
    "BrowseableEntry",
    "Collection",
    "Entity",
    "Entry",
    "Media",
    "Provider",
    "Role",
    "State",
    "User",
]


class Role(StrEnum):
    """Generic roles for entries in a browsable hierarchy."""

    BRANCH = "branch"
    LEAF = "leaf"
    ROOT = "root"
    STANDALONE = "standalone"


@dataclass(frozen=True, slots=True)
class Activity:
    """Observed user activity for an entry."""

    key: Key
    at: datetime


class State(ABC):
    """Provider-defined state exposed by entries."""

    @property
    @abstractmethod
    def is_empty(self) -> bool:
        """Return whether the state represents an untracked entry."""
        ...

    @classmethod
    @abstractmethod
    def deserialize(cls, state: SerializedState) -> Self:
        """Build state from a stable serialized representation."""
        ...

    @abstractmethod
    def serialize(self) -> SerializedState:
        """Return a stable serialized representation of the state."""
        ...


@dataclass(frozen=True, slots=True)
class User:
    """User or account identity associated with a provider."""

    key: Key
    title: str = field(compare=False)

    def __hash__(self) -> int:
        """Return a stable hash based on the user key."""
        return hash(self.key)


class Provider(ABC):
    """Minimal contract implemented by every AniBridge provider."""

    NAMESPACE: ClassVar[str]
    STATE_TYPE: ClassVar[type[State]]

    def __init__(
        self,
        *,
        logger: Logger,
        config: Mapping[str, object] | None = None,
    ) -> None:
        """Initialize the provider with a logger and raw config."""
        self.log = logger
        self.config: dict[str, object] = dict(config or {})

    async def initialize(self) -> None:
        """Run provider-specific async setup."""
        return None

    async def clear_cache(self) -> None:
        """Clear provider-local caches."""
        return None

    async def close(self) -> None:
        """Close provider resources."""
        return None

    @abstractmethod
    def user(self) -> User | None:
        """Return the authenticated user, if any."""
        ...


@dataclass(slots=True, eq=False)
class Entity[ProviderT: Provider](ABC):
    """Base class for provider-owned entities."""

    provider: ProviderT = field(repr=False, compare=False)
    key: Key
    title: str = field(compare=False)

    def __hash__(self) -> int:
        """Compute a hash from namespace, class, and key."""
        cls = type(self)
        return hash(
            (self.provider.NAMESPACE, cls.__module__, cls.__qualname__, self.key)
        )

    def __eq__(self, other: object) -> bool:
        """Compare entities by concrete class, namespace, and key."""
        if type(self) is not type(other):
            return NotImplemented
        other_entity = cast(Entity[Provider], other)
        return (
            self.provider.NAMESPACE == other_entity.provider.NAMESPACE
            and self.key == other_entity.key
        )

    def __repr__(self) -> str:
        """Return a short debug representation."""
        return (
            f"<{self.__class__.__name__}:{self.provider.NAMESPACE}:"
            f"{self.key}:{self.title[:32]}>"
        )


class Collection[ProviderT: Provider](Entity[ProviderT], ABC):
    """Logical collection of entries."""


class Media[ProviderT: Provider](Entity[ProviderT], ABC):
    """Shared metadata for entry media."""

    @property
    def kind(self) -> str | None:
        """Return a provider-defined kind label, if available."""
        return None

    @property
    def labels(self) -> Sequence[str]:
        """Return supplemental display labels."""
        return ()

    @property
    def poster(self) -> str | None:
        """Return a poster or cover URL, if available."""
        return None

    @property
    def url(self) -> str | None:
        """Return a direct URL to the provider page, if available."""
        return None


class Entry[ProviderT: Provider](Entity[ProviderT], ABC):
    """Base class for provider entries tied to media."""

    @property
    @abstractmethod
    def state(self) -> State:
        """Return the provider-defined state associated with the entry."""
        ...

    @abstractmethod
    def media(self) -> Media[ProviderT]:
        """Return the media metadata associated with the entry."""
        ...


class BrowseableEntry[ProviderT: Provider](Entry[ProviderT], ABC):
    """Entry observed from a browsable provider."""

    @abstractmethod
    async def events(self) -> Sequence[Activity]:
        """Return observed activity events for this entry."""
        ...

    @abstractmethod
    def refs(self) -> Sequence[MappingRef]:
        """Return cross-provider references for resolving this entry elsewhere."""
        ...

    def collection(self) -> Collection[ProviderT] | None:
        """Return the parent collection when the provider organizes entries."""
        return None

    def parent(self) -> BrowseableEntry[ProviderT] | None:
        """Return the direct parent entry, if any."""
        return None

    def children(self) -> Sequence[BrowseableEntry[ProviderT]]:
        """Return the direct child entries."""
        return ()

    @property
    def position(self) -> int | None:
        """Return the 1-based position among siblings, if available."""
        return None

    @property
    def role(self) -> Role:
        """Return the entry role in the observed hierarchy."""
        has_parent = self.parent() is not None
        has_children = bool(self.children())
        if has_parent and has_children:
            return Role.BRANCH
        if has_parent:
            return Role.LEAF
        if has_children:
            return Role.ROOT
        return Role.STANDALONE

    def ancestors(self) -> Sequence[BrowseableEntry[ProviderT]]:
        """Return ancestors ordered from the root to the direct parent."""
        ancestors: list[BrowseableEntry[ProviderT]] = []
        current = self.parent()
        while current is not None:
            ancestors.append(current)
            current = current.parent()
        ancestors.reverse()
        return tuple(ancestors)

    def descendants(self) -> Sequence[BrowseableEntry[ProviderT]]:
        """Return descendants in depth-first order."""
        descendants: list[BrowseableEntry[ProviderT]] = []
        for child in self.children():
            descendants.append(child)
            descendants.extend(child.descendants())
        return tuple(descendants)

    @property
    def depth(self) -> int:
        """Return the number of ancestor hops between this entry and the root."""
        return len(self.ancestors())
