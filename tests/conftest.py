"""Shared test scaffolding for provider contract tests."""

import logging
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Self, cast

import pytest

from anibridge.provider import (
    Activity,
    BrowseableEntry,
    Collection,
    Entry,
    Key,
    Logger,
    MappingRef,
    Media,
    Provider,
    ResolvedMapping,
    SerializedState,
    State,
    SupportsBackup,
    SupportsBrowse,
    SupportsDelete,
    SupportsGet,
    SupportsMappings,
    SupportsPut,
    SupportsSearch,
    SupportsWebhooks,
    User,
    WebhookPayload,
    WebhookResult,
)


@dataclass(frozen=True, slots=True)
class DummyObservedState(State):
    """Concrete observed state used by tests."""

    viewing: bool = False
    planned: bool = False
    review: str | None = None
    rating: int | None = None
    views: int = 0

    @property
    def is_empty(self) -> bool:
        return not (
            self.viewing
            or self.planned
            or self.review
            or self.rating is not None
            or self.views
        )

    @classmethod
    def deserialize(cls, state: SerializedState) -> Self:
        rating = state.get("rating")
        return cls(
            viewing=state.get("viewing") == "true",
            planned=state.get("planned") == "true",
            review=state.get("review"),
            rating=int(rating) if rating is not None else None,
            views=int(state.get("views", "0")),
        )

    def serialize(self) -> SerializedState:
        state: dict[str, str] = {
            "planned": str(self.planned).lower(),
            "viewing": str(self.viewing).lower(),
            "views": str(self.views),
        }
        if self.review is not None:
            state["review"] = self.review
        if self.rating is not None:
            state["rating"] = str(self.rating)
        return state


class DummyTrackedState(State):
    """Private tracked state used by the dummy tracked provider."""

    @property
    def is_empty(self) -> bool:
        return not self._values

    @classmethod
    def deserialize(cls, state: SerializedState) -> Self:
        return cls(state)

    def __init__(self, values: SerializedState) -> None:
        self._values = dict(values)

    def serialize(self) -> SerializedState:
        return dict(self._values)


class DummyCollection(Collection["DummySourceProvider"]):
    """Concrete collection used by tests."""

    provider: DummySourceProvider
    key: Key
    title: str

    def __init__(self, provider: DummySourceProvider) -> None:
        self.provider = provider
        self.key = "collection-1"
        self.title = "Anime"


class DummyTrackedMedia(Media["DummyTrackedProvider"]):
    """Concrete media metadata for tracked entries."""

    provider: DummyTrackedProvider
    key: Key
    title: str

    def __init__(self, provider: DummyTrackedProvider, key: Key) -> None:
        self.provider = provider
        self.key = key
        self.title = f"Media {key}"

    @property
    def kind(self) -> str | None:
        return "series"


class DummyObservedMedia(Media["DummySourceProvider"]):
    """Concrete media metadata for observed entries."""

    provider: DummySourceProvider
    key: Key
    title: str

    def __init__(self, provider: DummySourceProvider, key: Key) -> None:
        self.provider = provider
        self.key = key
        self.title = f"Observed {key}"


class DummyRootEntry(BrowseableEntry["DummySourceProvider"]):
    """Concrete root entry used by tests."""

    provider: DummySourceProvider
    key: Key
    title: str

    def __init__(
        self,
        provider: DummySourceProvider,
        collection: DummyCollection,
        key: Key,
    ) -> None:
        self.provider = provider
        self._collection = collection
        self.key = key
        self.title = "Dummy Root"
        self._media = DummyObservedMedia(provider, key)
        branch = DummyBranchEntry(provider, collection, self, "branch-1", 1)
        DummyLeafEntry(provider, collection, branch, "leaf-2", 2)
        self._children = (branch,)

    async def events(self) -> Sequence[Activity]:
        return (Activity(key=self.key, at=datetime(2026, 5, 10, tzinfo=UTC)),)

    def refs(self) -> Sequence[MappingRef]:
        return (MappingRef(provider="anilist", id="1"),)

    @property
    def state(self) -> State:
        return DummyObservedState(
            viewing=True,
            planned=False,
            review="Solid",
            rating=91,
            views=2,
        )

    def collection(self) -> DummyCollection:
        return self._collection

    def media(self) -> DummyObservedMedia:
        return self._media

    def children(self) -> Sequence[BrowseableEntry[DummySourceProvider]]:
        return self._children


class DummyBranchEntry(BrowseableEntry["DummySourceProvider"]):
    """Concrete intermediate entry used by tests."""

    provider: DummySourceProvider
    key: Key
    title: str

    def __init__(
        self,
        provider: DummySourceProvider,
        collection: DummyCollection,
        parent: DummyRootEntry,
        key: Key,
        position: int,
    ) -> None:
        self.provider = provider
        self._collection = collection
        self._parent = parent
        self.key = key
        self.title = "Dummy Branch"
        self._position = position
        self._media = DummyObservedMedia(provider, key)
        self._children: tuple[BrowseableEntry[DummySourceProvider], ...] = ()

    async def events(self) -> Sequence[Activity]:
        return ()

    def refs(self) -> Sequence[MappingRef]:
        return ()

    @property
    def state(self) -> State:
        return DummyObservedState(views=2)

    def collection(self) -> DummyCollection:
        return self._collection

    def media(self) -> DummyObservedMedia:
        return self._media

    def parent(self) -> DummyRootEntry:
        return self._parent

    def children(self) -> Sequence[BrowseableEntry[DummySourceProvider]]:
        return self._children

    @property
    def position(self) -> int | None:
        return self._position


class DummyLeafEntry(BrowseableEntry["DummySourceProvider"]):
    """Concrete leaf entry used by tests."""

    provider: DummySourceProvider
    key: Key
    title: str

    def __init__(
        self,
        provider: DummySourceProvider,
        collection: DummyCollection,
        parent: DummyBranchEntry,
        key: Key,
        position: int,
    ) -> None:
        self.provider = provider
        self._collection = collection
        self._parent = parent
        self.key = key
        self.title = "Dummy Leaf"
        self._position = position
        self._media = DummyObservedMedia(provider, key)
        parent._children = (self,)

    async def events(self) -> Sequence[Activity]:
        return ()

    def refs(self) -> Sequence[MappingRef]:
        return ()

    @property
    def state(self) -> State:
        return DummyObservedState(views=1)

    def collection(self) -> DummyCollection:
        return self._collection

    def media(self) -> DummyObservedMedia:
        return self._media

    def parent(self) -> DummyBranchEntry:
        return self._parent

    @property
    def position(self) -> int | None:
        return self._position


class DummyStandaloneEntry(BrowseableEntry["DummySourceProvider"]):
    """Concrete standalone entry used by tests."""

    provider: DummySourceProvider
    key: Key
    title: str

    def __init__(
        self,
        provider: DummySourceProvider,
        collection: DummyCollection,
        key: Key,
    ) -> None:
        self.provider = provider
        self._collection = collection
        self.key = key
        self.title = "Standalone"
        self._media = DummyObservedMedia(provider, key)

    async def events(self) -> Sequence[Activity]:
        return ()

    def refs(self) -> Sequence[MappingRef]:
        return ()

    @property
    def state(self) -> State:
        return DummyObservedState()

    def collection(self) -> DummyCollection:
        return self._collection

    def media(self) -> DummyObservedMedia:
        return self._media


class DummyTargetEntry(Entry["DummyTrackedProvider"]):
    """Concrete target-side entry used by tests."""

    provider: DummyTrackedProvider
    key: Key
    title: str

    def __init__(
        self,
        provider: DummyTrackedProvider,
        key: Key,
        state: SerializedState | None = None,
    ) -> None:
        self.provider = provider
        self.key = key
        self.title = f"Entry {key}"
        self._media = DummyTrackedMedia(provider, key)
        self._state = DummyTrackedState(
            state
            or {
                "progress": "1",
                "rating": "80",
                "repeats": "0",
                "started": datetime(2026, 5, 10, tzinfo=UTC).isoformat(),
                "status": "current",
            }
        )

    def media(self) -> DummyTrackedMedia:
        return self._media

    @property
    def state(self) -> State:
        return self._state


class DummySourceProvider(Provider, SupportsBrowse, SupportsWebhooks):
    """Concrete browsable provider used to test capability contracts."""

    NAMESPACE = "dummy-source"
    STATE_TYPE = DummyObservedState

    def __init__(self) -> None:
        super().__init__(
            logger=cast(Logger, logging.getLogger("tests.provider.source"))
        )

    async def collections(self) -> Sequence[Collection[Provider]]:
        return (cast(Collection[Provider], DummyCollection(self)),)

    async def entries(
        self,
        collection: Collection[Provider],
        *,
        keys: Sequence[Key] | None = None,
        updated_after: datetime | None = None,
        active_only: bool = False,
    ) -> AsyncIterator[BrowseableEntry[Provider]]:
        del active_only, keys, updated_after
        resolved_collection = cast(DummyCollection, collection)
        yield cast(
            BrowseableEntry[Provider],
            DummyRootEntry(self, resolved_collection, "root-1"),
        )

    def parse_webhook(self, payload: WebhookPayload) -> WebhookResult:
        del payload
        return WebhookResult(matched=True, keys=("root-1",))

    def user(self) -> User | None:
        return User(key="user-1", title="Source User")


class DummyTrackedProvider(
    Provider,
    SupportsBackup,
    SupportsDelete,
    SupportsGet,
    SupportsMappings,
    SupportsPut,
    SupportsSearch,
):
    """Concrete tracked provider used to test capability contracts."""

    NAMESPACE = "dummy-tracked"
    STATE_TYPE = DummyTrackedState
    MAPPING_PROVIDERS = frozenset({"anilist"})

    def __init__(self) -> None:
        super().__init__(
            logger=cast(Logger, logging.getLogger("tests.provider.tracked"))
        )

    async def delete(self, key: Key) -> None:
        del key
        return None

    async def export(self) -> str:
        return "{}"

    async def get(self, key: Key) -> Entry[Provider] | None:
        if key == "boom":
            raise RuntimeError("boom")
        if key == "missing":
            return None
        return cast(Entry[Provider], DummyTargetEntry(self, key))

    async def resolve_refs(
        self,
        refs: Sequence[MappingRef],
    ) -> Sequence[ResolvedMapping]:
        return tuple(ResolvedMapping(mapping=ref, key=ref.id) for ref in refs)

    async def restore(self, backup: str) -> None:
        del backup
        return None

    async def search(self, query: str) -> Sequence[Entry[Provider]]:
        del query
        return (cast(Entry[Provider], DummyTargetEntry(self, "search-1")),)

    def derive_state(
        self,
        entries: Sequence[BrowseableEntry[DummySourceProvider]],
    ) -> State:
        if not entries:
            raise ValueError("entries must not be empty")

        focus = entries[0]
        ancestors = focus.ancestors()
        root = ancestors[0] if ancestors else focus
        root_state = dict(root.state.serialize())
        focus_state = dict(focus.state.serialize())
        entry_states = [dict(entry.state.serialize()) for entry in entries]
        state: dict[str, str] = {
            "count": str(len(entries)),
            "focus_key": focus.key,
            "root_key": root.key,
        }
        progress = sum(
            int(entry_state.get("views", "0")) for entry_state in entry_states
        )
        if progress:
            state["progress"] = str(progress)
        if any(
            entry_state.get("viewing") == "true"
            for entry_state in (root_state, focus_state, *entry_states)
        ):
            state["status"] = "current"
        elif any(
            entry_state.get("planned") == "true"
            for entry_state in (root_state, focus_state, *entry_states)
        ):
            state["status"] = "planning"
        if review := (focus_state.get("review") or root_state.get("review")):
            state["review"] = review
        if rating := (focus_state.get("rating") or root_state.get("rating")):
            state["rating"] = rating
        return DummyTrackedState(state)

    async def put(
        self,
        key: Key,
        state: State,
    ) -> Entry[Provider] | None:
        if key == "boom":
            raise RuntimeError("boom")
        return cast(
            Entry[Provider],
            DummyTargetEntry(self, key, state.serialize()),
        )

    def user(self) -> User | None:
        return User(key="user-2", title="Tracked User")


@pytest.fixture
def webhook_payload() -> WebhookPayload:
    """Return a representative webhook payload for contract tests."""

    return WebhookPayload(
        body=b'{"event":"media.scrobble"}',
        headers={"content-type": "application/json"},
        method="POST",
        path="/webhook/provider",
    )


@pytest.fixture
def source_provider() -> DummySourceProvider:
    """Return a browsable dummy provider."""

    return DummySourceProvider()


@pytest.fixture
def tracked_provider() -> DummyTrackedProvider:
    """Return a tracked dummy provider."""

    return DummyTrackedProvider()


@pytest.fixture
def observed_collection(source_provider: DummySourceProvider) -> DummyCollection:
    """Return a dummy collection for observed hierarchy tests."""

    return DummyCollection(source_provider)


@pytest.fixture
def observed_root(
    source_provider: DummySourceProvider,
    observed_collection: DummyCollection,
) -> DummyRootEntry:
    """Return a root observed entry with nested descendants."""

    return DummyRootEntry(source_provider, observed_collection, "root-1")


@pytest.fixture
def standalone_entry(
    source_provider: DummySourceProvider,
    observed_collection: DummyCollection,
) -> DummyStandaloneEntry:
    """Return a standalone observed entry with no hierarchy relatives."""

    return DummyStandaloneEntry(source_provider, observed_collection, "standalone-1")


@pytest.fixture
def tracked_entry(tracked_provider: DummyTrackedProvider) -> DummyTargetEntry:
    """Return a tracked entry for state assertions."""

    return DummyTargetEntry(tracked_provider, "tracked-1")


@pytest.fixture
def ok_entries(observed_root: DummyRootEntry) -> list[DummyLeafEntry]:
    """Return derive_state entries whose derived state should succeed."""

    branch = cast(DummyBranchEntry, observed_root.children()[0])
    leaf = cast(DummyLeafEntry, branch.children()[0])
    return [leaf]


@pytest.fixture
def failing_entries(
    standalone_entry: DummyStandaloneEntry,
) -> list[DummyStandaloneEntry]:
    """Return derive_state entries for the failure-path state."""

    return [standalone_entry]
