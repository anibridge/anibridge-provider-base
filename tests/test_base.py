import asyncio
import logging
import re
from collections.abc import Callable
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from anibridge.provider.base import (
    Account,
    AppendEvent,
    Artwork,
    BackupArtifact,
    Capabilities,
    ChangeKind,
    DeleteEvent,
    DeleteRecord,
    Descriptor,
    EventChange,
    EventKind,
    ExternalId,
    FacetName,
    FieldSpec,
    Identifiers,
    InboundRequest,
    InboundResult,
    Metadata,
    Node,
    NodeChange,
    NodeFlag,
    NodeKind,
    NodeQuery,
    NumericConstraint,
    Page,
    Part,
    Progress,
    ProgressConstraint,
    Provider,
    Rating,
    Record,
    RecordChange,
    RecordField,
    RecordKind,
    Ref,
    Role,
    ScanItem,
    ScanQuery,
    Status,
    Step,
    Structure,
    SupportsBackupExports,
    SupportsBackupImports,
    SupportsChangeFeed,
    SupportsEventReads,
    SupportsEventSummaries,
    SupportsEventWrites,
    SupportsInboundChanges,
    SupportsMapping,
    SupportsNodeReads,
    SupportsNodeSearch,
    SupportsRecordReads,
    SupportsRecordWrites,
    SupportsScan,
    TemporalConstraint,
    TemporalPrecision,
    TextConstraint,
    Titles,
    UpsertRecord,
    WriteError,
    WriteOp,
    WriteResult,
)


def test_external_id_parse_and_descriptor_round_trip() -> None:
    assert ExternalId.parse("anilist:123") == ExternalId("anilist", "123")
    assert ExternalId.parse("tvdb:456:series") == ExternalId("tvdb", "456", "series")
    assert ExternalId("tmdb", "789", "movie").descriptor == "tmdb:789:movie"
    assert repr(ExternalId("mal", "42")) == "mal:42"


@pytest.mark.parametrize("descriptor", ["", "one", "a:b:c:d"])
def test_external_id_parse_rejects_invalid_descriptors(descriptor: str) -> None:
    with pytest.raises(ValueError, match="not a valid descriptor"):
        ExternalId.parse(descriptor)


def test_ref_helpers_build_anchor_and_part_paths() -> None:
    anchor = Ref.anchor("show-1")
    episode = Ref.at("show-1", ("season", 1), ("episode", 3))

    assert anchor.is_anchor is True
    assert repr(anchor) == "show-1"
    assert episode.is_anchor is False
    assert episode.path == (Step("season", 1), Step("episode", 3))
    assert repr(episode) == "show-1:season=1,episode=3"
    assert anchor.child("episode", 1) == Ref("show-1", (Step("episode", 1),))


def test_value_objects_are_frozen_and_slotted() -> None:
    ref = Ref.anchor("movie-1")

    with pytest.raises(FrozenInstanceError):
        ref.key = "movie-2"  # ty:ignore[invalid-assignment]

    with pytest.raises(AttributeError):
        ref.extra = "nope"  # ty:ignore[invalid-assignment]


def test_default_factories_are_independent_between_instances() -> None:
    first = NodeQuery()
    second = NodeQuery()

    assert first.refs == ()
    assert first.flags == frozenset()
    assert first.facets == frozenset()
    assert first.flags is not second.flags
    assert first.facets is not second.facets


def test_artwork_poster_reads_conventional_role() -> None:
    assert Artwork({"poster": "https://example.test/poster.jpg"}).poster == (
        "https://example.test/poster.jpg"
    )
    assert Artwork({"banner": "https://example.test/banner.jpg"}).poster is None


@pytest.mark.parametrize(
    ("constraint", "error"),
    [
        (
            lambda: NumericConstraint(step=0),
            "NumericConstraint.step must be > 0",
        ),
        (
            lambda: NumericConstraint(minimum=10, maximum=1),
            "NumericConstraint.minimum must be <= NumericConstraint.maximum",
        ),
        (
            lambda: TextConstraint(max_length=-1),
            "TextConstraint.max_length must be >= 0",
        ),
        (
            lambda: BackupArtifact(b"{}", file_extension="json"),
            "BackupArtifact.file_extension must start with '.'",
        ),
    ],
)
def test_constraint_invariants_are_validated(
    constraint: Callable[[], object], error: str
) -> None:
    with pytest.raises(ValueError, match=error):
        constraint()


def test_valid_constraints_and_backup_artifact_are_accepted() -> None:
    assert NumericConstraint(minimum=0, maximum=10, step=0.5).step == 0.5
    assert TextConstraint(max_length=100).max_length == 100
    assert (
        ProgressConstraint(current=NumericConstraint(minimum=0), total=False).total
        is False
    )
    assert BackupArtifact(b"payload", ".zip", "application/zip").media_type == (
        "application/zip"
    )


def test_field_spec_requires_status_values_for_status_fields() -> None:
    with pytest.raises(
        ValueError, match="STATUS fields must declare supported native values"
    ):
        FieldSpec(RecordField.STATUS)


def test_field_spec_rejects_status_values_on_non_status_fields() -> None:
    with pytest.raises(
        ValueError,
        match=re.escape("FieldSpec.values is only valid for RecordField.STATUS"),
    ):
        FieldSpec(
            RecordField.NOTES,
            values=(Descriptor("Watching", Status.ACTIVE),),
        )


def test_field_spec_rejects_private_status_values() -> None:
    with pytest.raises(
        ValueError, match="STATUS field values must map to a normalized Status"
    ):
        FieldSpec(
            RecordField.STATUS,
            values=(Descriptor("Watching"),),
        )


def test_field_spec_rejects_duplicate_status_native_values() -> None:
    with pytest.raises(ValueError, match="duplicate STATUS native value: 'Watching'"):
        FieldSpec(
            RecordField.STATUS,
            values=(
                Descriptor("Watching", Status.ACTIVE),
                Descriptor("Watching", Status.COMPLETED),
            ),
        )


def test_field_spec_rejects_duplicate_writable_status_semantics() -> None:
    with pytest.raises(
        ValueError,
        match=re.escape("duplicate writable STATUS semantic: <Status.ACTIVE"),
    ):
        FieldSpec(
            RecordField.STATUS,
            writable=True,
            values=(
                Descriptor("Watching", Status.ACTIVE),
                Descriptor("In Progress", Status.ACTIVE),
            ),
        )


def test_field_spec_allows_duplicate_readonly_status_semantics() -> None:
    spec = FieldSpec(
        RecordField.STATUS,
        writable=False,
        values=(
            Descriptor("Watching", Status.ACTIVE),
            Descriptor("Rewatching", Status.ACTIVE),
        ),
    )

    assert spec.values[1].native == "Rewatching"


def test_field_spec_rejects_duplicate_constraint_types() -> None:
    with pytest.raises(
        ValueError, match="duplicate field constraint type: NumericConstraint"
    ):
        FieldSpec(
            RecordField.RATING,
            constraints=(
                NumericConstraint(minimum=0, maximum=10),
                NumericConstraint(step=0.5),
            ),
        )


def test_field_spec_accepts_mixed_constraints() -> None:
    spec = FieldSpec(
        RecordField.FINISHED_AT,
        constraints=(
            TemporalConstraint(TemporalPrecision.DATE),
            TextConstraint(max_length=16),
        ),
    )

    assert spec.constraints[0] == TemporalConstraint(TemporalPrecision.DATE)


def test_capabilities_can_describe_provider_vocabularies() -> None:
    status_spec = FieldSpec(
        RecordField.STATUS,
        writable=True,
        values=(
            Descriptor("watching", Status.ACTIVE),
            Descriptor("completed", Status.COMPLETED),
        ),
    )

    capabilities = Capabilities(
        roles=frozenset({Role.SOURCE, Role.TARGET}),
        facets=frozenset({FacetName.TITLES, FacetName.IDS}),
        node_kinds=(Descriptor("show", NodeKind.SERIES),),
        coordinate_axes={"show": ("season", "episode")},
        record_kinds=(Descriptor("progress", RecordKind.PROGRESS),),
        record_fields={RecordField.STATUS: status_spec},
        event_kinds=(Descriptor("play", EventKind.PLAY),),
        write_ops=frozenset({WriteOp.UPSERT_RECORD}),
        change_kinds=frozenset({ChangeKind.RECORD}),
        external_authorities=frozenset({"anilist"}),
    )

    assert capabilities.roles == frozenset({Role.SOURCE, Role.TARGET})
    assert capabilities.node_kinds[0].semantic is NodeKind.SERIES
    assert capabilities.coordinate_axes["show"] == ("season", "episode")
    assert capabilities.record_fields[RecordField.STATUS] is status_spec


def test_catalog_and_record_value_objects_keep_provider_data() -> None:
    ref = Ref.at("show-1", ("episode", 1))
    external_id = ExternalId("anilist", "100")
    node = Node(
        ref=ref,
        kind="episode",
        title="Episode 1",
        url="https://example.test/episode/1",
        labels=("dubbed",),
        flags=frozenset({NodeFlag.CONSUMABLE, NodeFlag.TRACKABLE}),
        facets={
            FacetName.TITLES: Titles("Main Title", {"ja": "Japanese Title"}),
            FacetName.ARTWORK: Artwork({"poster": "poster.jpg"}),
            FacetName.IDS: Identifiers((external_id,)),
            FacetName.STRUCTURE: Structure(
                ("episode",), (Part((Step("episode", 1),), "Episode 1"),)
            ),
            FacetName.METADATA: Metadata({"season_title": "Season One"}),
        },
    )
    record = Record(
        ref=ref,
        kind="progress",
        key="record-1",
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        ids=(external_id,),
        values={
            RecordField.STATUS: Status.ACTIVE.value,
            RecordField.PROGRESS: Progress(1, 12, "episode"),
            RecordField.RATING: Rating(8, (0, 10, 1)),
        },
        metadata={"source": "fixture"},
    )

    assert node.flags == frozenset({NodeFlag.CONSUMABLE, NodeFlag.TRACKABLE})
    assert node.facets[FacetName.IDS] == Identifiers((external_id,))
    assert record.values[RecordField.PROGRESS] == Progress(1, 12, "episode")


def test_pages_and_queries_hold_pagination_and_projection_state() -> None:
    ref = Ref.anchor("show-1")
    node = Node(ref, "show")
    record = Record(ref)
    scan_item = ScanItem(node, (record,))

    node_page = Page((node,), cursor="next", total=2)
    scan_query = ScanQuery(
        sources=(ref,),
        flags=frozenset({NodeFlag.SCAN_ROOT}),
        facets=frozenset({FacetName.TITLES}),
        fields=frozenset({RecordField.STATUS}),
        require_activity=True,
        limit=25,
    )

    assert node_page.items == (node,)
    assert node_page.cursor == "next"
    assert scan_item.records == (record,)
    assert scan_query.sources == (ref,)
    assert scan_query.require_activity is True


def test_write_and_change_dtos_preserve_correlation_and_error_details() -> None:
    ref = Ref.anchor("show-1")
    now = datetime(2026, 6, 13, tzinfo=UTC)

    upsert = UpsertRecord(
        ref,
        kind="progress",
        key="record-1",
        token="tok-1",
        expected_revision="rev-1",
        set={RecordField.STATUS: Status.COMPLETED.value},
        clear=frozenset({RecordField.NOTES}),
    )
    delete_record = DeleteRecord(ref=ref, kind="progress", token="tok-2")
    append_event = AppendEvent(ref, "play", now, token="tok-3")
    delete_event = DeleteEvent(ref=ref, kind="play", at=now, token="tok-4")
    result = WriteResult(
        ok=False,
        op=WriteOp.UPSERT_RECORD,
        token="tok-1",
        ref=ref,
        code=WriteError.CONFLICT,
        error="stale revision",
    )

    assert upsert.expected_revision == "rev-1"
    assert delete_record.token == "tok-2"
    assert append_event.at == now
    assert delete_event.kind == "play"
    assert result.code is WriteError.CONFLICT


def test_change_and_inbound_dtos_keep_notifications_framework_agnostic() -> None:
    ref = Ref.anchor("show-1")
    now = datetime(2026, 6, 13, tzinfo=UTC)
    changes = (
        NodeChange(ref=ref, at=now, facets=frozenset({FacetName.TITLES})),
        RecordChange(ref=ref, kind="progress", fields=frozenset({RecordField.STATUS})),
        EventChange(ref=ref, kind="play", at=now),
    )
    request = InboundRequest(
        method="POST",
        path="/webhook",
        headers={"x-signature": "abc"},
        query={"debug": ("1",)},
        body=b"{}",
    )
    result = InboundResult(matched=True, changes=changes)

    assert request.query["debug"] == ("1",)
    assert result.changes == changes


class MinimalProvider(Provider):
    DISPLAY_NAME = "Minimal"
    NAMESPACE = "minimal"

    def account(self) -> Account | None:
        return Account("acct-1", "Test Account")


def test_provider_base_stores_config_and_has_default_async_lifecycle() -> None:
    logger = logging.getLogger("tests.provider")
    provider = MinimalProvider(logger=logger, config={"token": "secret"})

    assert provider.log is logger
    assert provider.config == {"token": "secret"}
    assert provider.account() == Account("acct-1", "Test Account")
    assert provider.capabilities() == Capabilities()
    asyncio.run(provider.initialize())
    asyncio.run(provider.clear_cache())
    asyncio.run(provider.close())


def test_provider_copies_config_mapping() -> None:
    config = {"token": "initial"}
    provider = MinimalProvider(
        logger=logging.getLogger("tests.provider"), config=config
    )

    config["token"] = "changed"

    assert provider.config == {"token": "initial"}


@pytest.mark.parametrize(
    "mixin",
    [
        SupportsNodeReads,
        SupportsNodeSearch,
        SupportsScan,
        SupportsMapping,
        SupportsRecordReads,
        SupportsRecordWrites,
        SupportsEventReads,
        SupportsEventSummaries,
        SupportsEventWrites,
        SupportsChangeFeed,
        SupportsBackupExports,
        SupportsBackupImports,
        SupportsInboundChanges,
    ],
)
def test_support_mixins_are_abstract(mixin: type) -> None:
    with pytest.raises(TypeError):
        mixin()
