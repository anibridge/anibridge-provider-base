"""Tests for the AniBridge provider base contract."""

import inspect
import logging
import re
from collections.abc import Callable
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from typing import Any

import pytest

from anibridge.provider.base import (
    Account,
    AppendEvent,
    Artwork,
    BackupArtifact,
    Capabilities,
    ChangeKind,
    DeleteEvent,
    Descriptor,
    EventChange,
    EventKind,
    EventSpec,
    EventWriteOp,
    ExternalId,
    FacetName,
    FieldConstraint,
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
    NodeSpec,
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
    RecordQuery,
    RecordSpec,
    RecordUnit,
    RecordWriteOp,
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
        pytest.param(
            lambda: NumericConstraint(step=0),
            "NumericConstraint.step must be > 0",
            id="zero-step",
        ),
        pytest.param(
            lambda: NumericConstraint(minimum=10, maximum=1),
            "NumericConstraint.minimum must be <= NumericConstraint.maximum",
            id="inverted-range",
        ),
        pytest.param(
            lambda: TextConstraint(max_length=-1),
            "TextConstraint.max_length must be >= 0",
            id="negative-text-limit",
        ),
        pytest.param(
            lambda: BackupArtifact(b"{}", file_extension="json"),
            "BackupArtifact.file_extension must start with '.'",
            id="bad-extension",
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


@pytest.mark.parametrize(
    ("field", "constraint"),
    [
        (RecordField.STATUS, TextConstraint(max_length=10)),
        (RecordField.PROGRESS, NumericConstraint(0, 10, 1)),
        (RecordField.RATING, TextConstraint(max_length=10)),
        (RecordField.REPEAT_COUNT, TextConstraint(max_length=10)),
        (
            RecordField.STARTED_AT,
            NumericConstraint(0, 10, 1),
        ),
        (RecordField.NOTES, NumericConstraint(0, 10, 1)),
    ],
)
def test_field_spec_rejects_constraints_for_wrong_field(
    field: RecordField,
    constraint: FieldConstraint,
) -> None:
    with pytest.raises(
        ValueError,
        match=re.escape(f"{type(constraint).__name__} is not valid for {field.value}"),
    ):
        FieldSpec(
            field,
            readable=False,
            writable=False,
            constraints=(constraint,),
        )


def test_field_spec_accepts_constraints_for_matching_field_types() -> None:
    FieldSpec(
        RecordField.PROGRESS,
        constraints=(ProgressConstraint(current=NumericConstraint(0, None, 1)),),
    )
    FieldSpec(RecordField.RATING, constraints=(NumericConstraint(0, 10, 1),))
    FieldSpec(RecordField.REPEAT_COUNT, constraints=(NumericConstraint(0, None, 1),))
    FieldSpec(
        RecordField.STARTED_AT,
        constraints=(TemporalConstraint(TemporalPrecision.DATE),),
    )
    FieldSpec(RecordField.NOTES, constraints=(TextConstraint(max_length=1000),))


def test_specs_reject_mismatched_fields_and_wrong_write_ops() -> None:
    with pytest.raises(
        ValueError,
        match=re.escape("RecordSpec.fields keys must match FieldSpec.field"),
    ):
        RecordSpec(
            "user_state",
            fields={RecordField.STATUS: FieldSpec(RecordField.NOTES)},
        )

    with pytest.raises(ValueError, match="contains event operations"):
        RecordSpec(
            "user_state",
            write_ops=frozenset[Any]({EventWriteOp.APPEND}),
        )

    with pytest.raises(
        ValueError,
        match=re.escape("RecordSpec.surface must name a record surface"),
    ):
        RecordSpec("")

    with pytest.raises(ValueError, match="contains record operations"):
        EventSpec(
            Descriptor("scrobble", EventKind.SCROBBLE),
            write_ops=frozenset[Any]({RecordWriteOp.UPSERT}),
        )


def test_capabilities_describe_current_provider_vocabularies() -> None:
    status_spec = FieldSpec(
        RecordField.STATUS,
        writable=True,
        values=(
            Descriptor("watching", Status.ACTIVE),
            Descriptor("completed", Status.COMPLETED),
        ),
    )
    node_spec = NodeSpec(
        Descriptor("show", NodeKind.SERIES),
        flags=frozenset({NodeFlag.ANCHOR}),
        coordinate_axes=("season", "episode"),
    )
    record_spec = RecordSpec(
        "user_state",
        fields={RecordField.STATUS: status_spec},
        write_ops=frozenset({RecordWriteOp.UPSERT}),
    )
    event_spec = EventSpec(
        Descriptor("scrobble", EventKind.SCROBBLE),
        write_ops=frozenset({EventWriteOp.APPEND, EventWriteOp.DELETE}),
        idempotent_appends=True,
    )

    capabilities = Capabilities(
        roles=frozenset({Role.SOURCE, Role.TARGET}),
        facets=frozenset({FacetName.TITLES, FacetName.IDS}),
        nodes=(node_spec,),
        records=(record_spec,),
        events=(event_spec,),
        change_kinds=frozenset({ChangeKind.RECORD}),
        external_authorities=frozenset({"anilist"}),
    )

    assert capabilities.nodes[0].kind.semantic is NodeKind.SERIES
    assert capabilities.nodes[0].coordinate_axes == ("season", "episode")
    assert capabilities.records[0].fields[RecordField.STATUS] is status_spec
    assert capabilities.events[0].kind.semantic is EventKind.SCROBBLE


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
        surface="user_state",
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


def test_record_rejects_duplicate_unit_indexes() -> None:
    with pytest.raises(
        ValueError,
        match=re.escape("Record.units indexes must be unique"),
    ):
        Record(
            Ref.anchor("show-1"),
            "user_state",
            units=(RecordUnit(1), RecordUnit(1)),
        )


def test_pages_and_queries_hold_pagination_and_projection_state() -> None:
    ref = Ref.anchor("show-1")
    node = Node(ref, "show")
    record = Record(ref, "user_state")
    scan_item = ScanItem(node, (record,))

    node_page = Page((node,), cursor="next", total=2)
    scan_query = ScanQuery(
        sources=(ref,),
        flags=frozenset({NodeFlag.SCAN_ROOT}),
        facets=frozenset({FacetName.TITLES}),
        record_surfaces=frozenset({"user_state"}),
        record_fields=frozenset({RecordField.STATUS}),
        require_user_data=True,
        limit=25,
    )
    record_query = RecordQuery(
        refs=(ref,),
        record_surfaces=("user_state",),
        fields=frozenset({RecordField.STATUS}),
    )

    assert node_page.items == (node,)
    assert node_page.cursor == "next"
    assert scan_item.records == (record,)
    assert scan_query.sources == (ref,)
    assert scan_query.require_user_data is True
    assert record_query.record_surfaces == ("user_state",)


def test_write_and_change_dtos_preserve_correlation_and_error_details() -> None:
    ref = Ref.anchor("show-1")
    now = datetime(2026, 6, 13, tzinfo=UTC)

    upsert = UpsertRecord(
        ref,
        surface="user_state",
        key="record-1",
        token="tok-1",
        expected_revision="rev-1",
        set={RecordField.STATUS: Status.COMPLETED.value},
        clear=frozenset({RecordField.NOTES}),
    )
    append_event = AppendEvent(ref, "scrobble", now, token="tok-2", dedupe_key="d1")
    delete_event = DeleteEvent(ref, "scrobble", now, token="tok-3", dedupe_key="d1")
    result = WriteResult(
        ok=False,
        op=RecordWriteOp.UPSERT,
        token="tok-1",
        ref=ref,
        code=WriteError.CONFLICT,
        error="stale revision",
    )

    assert upsert.expected_revision == "rev-1"
    assert append_event.dedupe_key == "d1"
    assert delete_event.dedupe_key == "d1"
    assert result.error == "stale revision"
    assert NodeChange(ref=ref, at=now).at == now
    assert RecordChange(ref=ref, surface="user_state", at=now).surface == "user_state"
    assert EventChange(ref=ref, kind="scrobble", at=now).kind == "scrobble"
    assert InboundResult(True, (NodeChange(ref=ref),)).matched is True
    assert InboundRequest("POST", "/hook", body=b"{}").body == b"{}"

    with pytest.raises(ValueError, match="DeleteEvent requires"):
        DeleteEvent(ref=ref, kind="scrobble")


def test_provider_base_stores_logger_and_config() -> None:
    class TestProvider(Provider):
        DISPLAY_NAME = "Test"
        NAMESPACE = "test"

        def account(self) -> Account | None:
            return None

    provider = TestProvider(logger=logging.getLogger("test-provider"), config={"x": 1})

    assert provider.config == {"x": 1}
    assert provider.account() is None


@pytest.mark.parametrize(
    ("protocol", "method_name"),
    [
        pytest.param(SupportsScan, "scan", id="scan"),
        pytest.param(SupportsNodeReads, "fetch_nodes", id="node-reads"),
        pytest.param(SupportsNodeSearch, "search_nodes", id="node-search"),
        pytest.param(SupportsRecordReads, "fetch_records", id="record-reads"),
        pytest.param(SupportsRecordWrites, "write_records", id="record-writes"),
        pytest.param(SupportsEventReads, "fetch_events", id="event-reads"),
        pytest.param(SupportsEventWrites, "write_events", id="event-writes"),
        pytest.param(SupportsChangeFeed, "poll_changes", id="change-feed"),
        pytest.param(SupportsMapping, "resolve", id="mapping"),
        pytest.param(SupportsInboundChanges, "parse_inbound", id="inbound"),
        pytest.param(SupportsBackupExports, "export_backup", id="backup-export"),
        pytest.param(SupportsBackupImports, "import_backup", id="backup-import"),
    ],
)
def test_protocol_methods_are_async(protocol: type[object], method_name: str) -> None:
    assert inspect.iscoroutinefunction(getattr(protocol, method_name))
