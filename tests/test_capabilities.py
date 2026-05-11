"""Tests for anibridge.provider.capabilities."""

import asyncio

from anibridge.provider import (
    MappingRef,
    ResolvedMapping,
    User,
    WebhookResult,
)


def test_collection_and_webhook_capabilities(source_provider, webhook_payload) -> None:
    """Collection browsing and webhook parsing should work through capabilities."""

    assert source_provider.user() == User(key="user-1", title="Source User")
    assert source_provider.parse_webhook(webhook_payload) == WebhookResult(
        matched=True,
        keys=("root-1",),
    )

    collections = asyncio.run(source_provider.collections())
    assert [collection.key for collection in collections] == ["collection-1"]

    async def collect_entry_keys() -> list[str]:
        return [entry.key async for entry in source_provider.entries(collections[0])]

    assert asyncio.run(collect_entry_keys()) == ["root-1"]


def test_tracked_capabilities_preserve_order_and_tolerate_failures(
    tracked_provider,
    ok_entries,
    failing_entries,
) -> None:
    """Tracked entry helpers should preserve order and tolerate per-entry failures."""

    assert tracked_provider.user() == User(
        key="user-2",
        title="Tracked User",
    )
    assert asyncio.run(tracked_provider.export()) == "{}"
    assert asyncio.run(tracked_provider.restore("{}")) is None
    assert [
        entry.key if entry else None
        for entry in asyncio.run(tracked_provider.get_many(("ok", "missing", "boom")))
    ] == ["ok", None, None]
    assert asyncio.run(tracked_provider.search("naruto"))[0].key == "search-1"
    assert asyncio.run(
        tracked_provider.resolve_refs((MappingRef(provider="anilist", id="123"),))
    ) == (
        ResolvedMapping(
            mapping=MappingRef(provider="anilist", id="123"),
            key="123",
        ),
    )
    ok_state = tracked_provider.derive_state(ok_entries)
    failing_state = tracked_provider.derive_state(failing_entries)

    assert ok_state.serialize() == {
        "count": "1",
        "focus_key": "leaf-2",
        "progress": "1",
        "rating": "91",
        "review": "Solid",
        "root_key": "root-1",
        "status": "current",
    }
    updated_entries = asyncio.run(
        tracked_provider.put_many((("ok", ok_state), ("boom", failing_state)))
    )
    assert [entry.key if entry else None for entry in updated_entries] == ["ok", None]
    assert updated_entries[0].state.serialize() == {
        "count": "1",
        "focus_key": "leaf-2",
        "progress": "1",
        "rating": "91",
        "review": "Solid",
        "root_key": "root-1",
        "status": "current",
    }
