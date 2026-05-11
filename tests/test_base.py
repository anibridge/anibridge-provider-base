"""Tests for anibridge.provider.base."""

import asyncio
from datetime import UTC, datetime

from anibridge.provider import (
    Activity,
    MappingRef,
    Role,
    User,
)


def test_provider_core_defaults(source_provider) -> None:
    """Base provider lifecycle hooks should remain safe no-ops by default."""

    assert asyncio.run(source_provider.initialize()) is None
    assert asyncio.run(source_provider.clear_cache()) is None
    assert asyncio.run(source_provider.close()) is None
    assert source_provider.user() == User(key="user-1", title="Source User")


def test_state_round_trips_through_deserialize(observed_root, tracked_entry) -> None:
    """Concrete state implementations should round-trip through the contract."""

    observed_state = observed_root.state
    tracked_state = tracked_entry.state

    assert (
        observed_root.provider.STATE_TYPE.deserialize(observed_state.serialize())
        == observed_state
    )
    assert (
        tracked_entry.provider.STATE_TYPE.deserialize(
            tracked_state.serialize()
        ).serialize()
        == tracked_state.serialize()
    )


def test_observed_entries_expose_expected_defaults_and_hierarchy(
    source_provider,
    observed_collection,
    observed_root,
    standalone_entry,
    tracked_entry,
) -> None:
    """Observed and tracked entries should expose the shared base helpers."""

    async def collect_entries() -> list:
        return [entry async for entry in source_provider.entries(observed_collection)]

    branch = observed_root.children()[0]
    leaf = branch.children()[0]
    fresh_root = asyncio.run(collect_entries())[0]

    assert observed_root.media().url is None
    assert observed_root.media().labels == ()
    assert observed_root.media().kind is None
    assert observed_root.media().poster is None
    assert observed_root.refs() == (MappingRef(provider="anilist", id="1"),)
    assert observed_root.collection() is observed_collection
    assert observed_root.state.serialize() == {
        "planned": "false",
        "rating": "91",
        "review": "Solid",
        "viewing": "true",
        "views": "2",
    }
    assert asyncio.run(observed_root.events()) == (
        Activity(key="root-1", at=datetime(2026, 5, 10, tzinfo=UTC)),
    )
    assert observed_root == fresh_root
    assert hash(source_provider.user()) == hash("user-1")
    assert hash(observed_root) == hash(
        (
            observed_root.provider.NAMESPACE,
            type(observed_root).__module__,
            type(observed_root).__qualname__,
            observed_root.key,
        )
    )

    assert observed_root.role == Role.ROOT
    assert observed_root.ancestors() == ()
    assert observed_root.children() == (branch,)
    assert observed_root.descendants() == (branch, leaf)
    assert observed_root.depth == 0

    assert branch.role == Role.BRANCH
    assert branch.parent() is observed_root
    assert branch.position == 1
    assert branch.ancestors() == (observed_root,)
    assert branch.children() == (leaf,)
    assert branch.descendants() == (leaf,)
    assert branch.depth == 1

    assert leaf.role == Role.LEAF
    assert leaf.parent() is branch
    assert leaf.position == 2
    assert leaf.ancestors() == (observed_root, branch)
    assert leaf.children() == ()
    assert leaf.descendants() == ()
    assert leaf.depth == 2

    assert standalone_entry.role == Role.STANDALONE
    assert standalone_entry.parent() is None
    assert standalone_entry.children() == ()
    assert standalone_entry.ancestors() == ()
    assert standalone_entry.descendants() == ()
    assert standalone_entry.depth == 0

    assert tracked_entry.media().kind == "series"
    assert tracked_entry.state.serialize() == {
        "progress": "1",
        "rating": "80",
        "repeats": "0",
        "started": "2026-05-10T00:00:00+00:00",
        "status": "current",
    }
