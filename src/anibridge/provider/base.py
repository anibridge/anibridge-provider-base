"""Provider contracts for AniBridge provider authors.

This module defines the interface between AniBridge and a concrete media provider
(Plex, AniList, Trakt, Jellyfin, MAL, and similar services).

Providers translate their native catalog, identity, aggregate user state, activity
events, constraints, and write behavior into the normalized objects in this module.
The contract is deliberately strict about semantics: AniBridge plans from these values,
so every field must mean the same thing regardless of provider.

----------------------------------------------------------------------------------------
Implementation guide
----------------------------------------------------------------------------------------

1. Start with identity: anchors, refs, and paths

    The mappable unit is an anchor (a show, movie, manga, book series, game, or similar)
    work. A `Ref` addresses that anchor by `key`. A `Ref` may include a `path` of
    `Step`s into the anchor's coordinate space, such as season/episode/chapter.

    Use the same anchor key for every coordinate inside the same work. Add path steps
    when the provider exposes or accepts state below the anchor level.

    This lets AniBridge align providers that model parts differently. For example, one
    provider may expose distinct episode objects, while another only exposes aggregate
    "12 episodes watched" state. Both still describe the same anchor plus coordinate
    space.

2. Keep catalog, state, and activity separate

    `Node` is catalog data. It describes what exists, how it is identified, and what
    coordinate space it has.

    `Record` is current aggregate user state about a ref on a provider-local record
    surface, such as `media_list`, `anime_list`, or `user_state`. A surface names the
    native state API/table/object family a provider reads or writes; it is a dispatch
    handle, not sync semantics. Records are
    compared as latest state.

    `Event` is immutable timestamped activity in a named activity channel, such as a
    scrobble, check-in, rating, review, collection, or watchlist occurrence. Events are
    compared as occurrences. Event-based providers should expose events directly
    instead of forcing them into records.

3. Advertise native vocabularies through capabilities

    Provider-native names are open strings. Use them in `Node.kind`,
    `Record.surface`, `Event.kind`, `Step.axis`, `Progress.unit`, and artwork roles.

    Closed enums are the values AniBridge reasons over: `Status`, `RecordField`,
    `NodeFlag`, `FacetName`, `ChangeAction`, `WriteOp`, `TemporalPrecision`,
    `WriteError`, and the semantic kind enums `NodeKind` and `EventKind`.

    In `capabilities()`, describe each supported node kind, record surface, and event
    channel. Node and event specs map native strings to closed semantics. Record specs
    keep provider-native surfaces as opaque dispatch handles and advertise field
    capabilities; AniBridge matches records by compatible `RecordField` names rather
    than by provider surface names.

    Use `semantic=None` for native values that should be kept for display or round-trip
    fidelity, but never used for cross-provider sync.

4. Put operational node meaning in flags

    `NodeKind` describes what a node is for display, grouping, and coordinate
    interpretation. `NodeFlag` describes how AniBridge may operate on that node.

    A provider should attach flags based on the behavior the node supports:

    `ANCHOR`: the root work-level node AniBridge maps across providers, such as a show,
    movie, manga, book series, or game.

    `CONTAINER`: a node that can expand into addressable children or parts, such as a
    show with seasons, a season with episodes, or a book series with volumes.

    `CONSUMABLE`: a leaf a user can complete, such as an episode, movie, chapter,
    track, or other playable/readable unit.

    `TRACKABLE`: a ref that can hold user state or activity.

    `ORDERED_PARTS`: a node whose part coordinates have meaningful order, such as
    episode number, chapter number, disc/track order, or similar progress positions.

    `SCAN_ROOT`: a node that is valid as a starting point for bulk enumeration through
    `scan`.

    A node may have multiple flags. For example, a TV series is often both an `ANCHOR`
    and a `CONTAINER`, while an episode is often both `CONSUMABLE` and `TRACKABLE`.

5. Hydrate only the requested projection

    `Node.title`, `Node.url`, `Record.updated_at`, and `Event.at` should be cheap values
    that are always safe to return.

    Facets such as `TITLES`, `ARTWORK`, `IDS`, `STRUCTURE`, and `METADATA` are hydrated
    only when requested. Record fields and event metadata follow the same rule through
    their query projections.

    Returned objects are frozen value objects, not lazy proxies. Attribute access must
    never perform I/O. To load more data, query the same `Ref` again with a wider
    projection, preferably batched across many refs.

6. Keep metadata opaque

    Every `metadata: Mapping[str, MetaValue]` is provider passthrough. AniBridge does
    not plan from it, compare it, or translate it. Metadata is only for display,
    diagnostics, or provider-specific round trips.

    If the bridge must understand a value, model it as a normalized field, facet, flag,
    descriptor, constraint, or channel spec instead of putting it in metadata.

7. Normalize temporal values and constraints

    Every datetime crossing this contract must be timezone-aware UTC. A naive datetime
    is a contract violation. Date-precision values should be represented as `date`, not
    as artificial midnight datetimes.

    If a provider only supports date-level precision, advertise that with
    `TemporalConstraint(precision=TemporalPrecision.DATE)` in the relevant field or
    event spec.

    Use constraints to describe what the provider can represent or accept: date-vs-
    datetime precision, numeric range and step, text length, progress shape, event
    windows, and similar limits. Temporal constraints also tell the bridge how to
    translate between date and datetime providers.

8. Make record and event syncing first class

    A record-based sync compares `Record` values and writes `RecordWrite`s.

    An event-based sync compares `Event` occurrences and writes `EventWrite`s. Event
    channels advertise whether events have stable keys and whether repeated append
    attempts are idempotent, so the planner can replicate events without filtering away
    legitimate activity.

    A record-to-event or event-to-record sync is a translation between different
    models. It is allowed, but it should be explicit in the planner instead of being the
    hidden default contract shape.

9. Separate method presence from method granularity

    Add `SupportsX` mixins for the methods your provider implements. For example, use
    `SupportsScan` for bulk enumeration, `SupportsRecordReads` for record reads,
    `SupportsEventReads` for event reads, and `SupportsEventWrites` for event writes.

    Use `capabilities()` to describe what those methods can actually do: roles, facets,
    native kind mappings, coordinate axes, record surfaces, event channels, write
    operations, change kinds, and external authorities. `isinstance(provider,
    SupportsX)` says a method exists, while `capabilities()` says what it supports.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import StrEnum
from logging import Logger
from typing import ClassVar

__all__ = [
    "Account",
    "AppendEvent",
    "Artwork",
    "BackupArtifact",
    "Capabilities",
    "Change",
    "ChangeAction",
    "ChangeKind",
    "ChangeQuery",
    "DeleteRecord",
    "Descriptor",
    "Event",
    "EventChange",
    "EventKind",
    "EventQuery",
    "EventSpec",
    "EventWrite",
    "ExternalId",
    "Facet",
    "FacetName",
    "FieldConstraint",
    "FieldSpec",
    "Identifiers",
    "InboundRequest",
    "InboundResult",
    "Match",
    "MetaValue",
    "Metadata",
    "Node",
    "NodeChange",
    "NodeFlag",
    "NodeKind",
    "NodeQuery",
    "NodeSpec",
    "NumericConstraint",
    "Page",
    "Part",
    "Progress",
    "ProgressConstraint",
    "Provider",
    "Rating",
    "Record",
    "RecordChange",
    "RecordField",
    "RecordQuery",
    "RecordSpec",
    "RecordUnit",
    "RecordWrite",
    "Ref",
    "Role",
    "Scalar",
    "ScalarValue",
    "ScanItem",
    "ScanQuery",
    "Semantic",
    "State",
    "Status",
    "Step",
    "Structure",
    "SupportsBackupExports",
    "SupportsBackupImports",
    "SupportsChangeFeed",
    "SupportsEventReads",
    "SupportsEventWrites",
    "SupportsInboundChanges",
    "SupportsMapping",
    "SupportsNodeReads",
    "SupportsNodeSearch",
    "SupportsRecordReads",
    "SupportsRecordWrites",
    "SupportsScan",
    "TemporalConstraint",
    "TemporalPrecision",
    "TextConstraint",
    "Titles",
    "UpsertRecord",
    "Value",
    "WriteError",
    "WriteOp",
    "WriteResult",
]

type Scalar = str | int | float | bool
type ScalarValue = Scalar | None
type MetaValue = ScalarValue | tuple[ScalarValue, ...]


def _validate_utc(value: datetime | None, field_name: str) -> None:
    """Reject naive or non-UTC datetimes."""
    if value is None:
        return
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{field_name} must be timezone-aware UTC")


def _validate_record_values(values: Mapping[RecordField, Value]) -> None:
    """Validate record values that the type system cannot fully express."""
    for field_name, value in values.items():
        if value is None:
            raise ValueError(f"Record value {field_name} must not be None")
        if field_name == RecordField.LAST_ACTIVITY_AT:
            if not isinstance(value, datetime):
                raise ValueError("LAST_ACTIVITY_AT must be a datetime")
            _validate_utc(value, "Record.values[LAST_ACTIVITY_AT]")
        elif isinstance(value, datetime):
            _validate_utc(value, f"Record.values[{field_name}]")


def _validate_status_values(
    values: tuple[Descriptor[Status], ...], *, writable: bool
) -> None:
    """Validate native status descriptor declarations."""
    seen_writable_semantics: set[Status] = set()
    for descriptor in values:
        if descriptor.semantic is None:
            raise ValueError("STATUS field values must map to a normalized Status")
        if not writable:
            continue
        if descriptor.semantic in seen_writable_semantics:
            raise ValueError(
                f"duplicate writable STATUS semantic: {descriptor.semantic!r}"
            )
        seen_writable_semantics.add(descriptor.semantic)


def _validate_field_constraints(
    field_name: RecordField,
    constraints: tuple[FieldConstraint, ...],
) -> None:
    """Reject constraints that do not match a record field's value shape."""
    _validate_unique_constraints(constraints)
    if field_name == RecordField.PROGRESS:
        allowed = (ProgressConstraint,)
    elif field_name in (RecordField.RATING, RecordField.REPEAT_COUNT):
        allowed = (NumericConstraint,)
    elif field_name in (
        RecordField.STARTED_AT,
        RecordField.FINISHED_AT,
        RecordField.LAST_ACTIVITY_AT,
    ):
        allowed = (TemporalConstraint,)
    elif field_name == RecordField.NOTES:
        allowed = (TextConstraint,)
    else:
        allowed = ()

    for constraint in constraints:
        if not isinstance(constraint, allowed):
            raise ValueError(
                f"{type(constraint).__name__} is not valid for {field_name.value}"
            )


def _validate_unique_constraints(constraints: tuple[FieldConstraint, ...]) -> None:
    """Reject duplicate constraint types in one spec."""
    seen: set[type[FieldConstraint]] = set()
    for constraint in constraints:
        constraint_type = type(constraint)
        if constraint_type in seen:
            raise ValueError(f"duplicate constraint type: {constraint_type.__name__}")
        seen.add(constraint_type)


class Role(StrEnum):
    """Direction a provider may serve in a sync."""

    SOURCE = "source"
    TARGET = "target"


class NodeFlag(StrEnum):
    """Operational semantics the sync engine needs, attached to a catalog node."""

    ANCHOR = "anchor"
    CONTAINER = "container"
    CONSUMABLE = "consumable"
    TRACKABLE = "trackable"
    ORDERED_PARTS = "ordered_parts"
    SCAN_ROOT = "scan_root"


class Status(StrEnum):
    """Provider-neutral status for aggregate user state."""

    PLANNED = "planned"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    DROPPED = "dropped"
    REPEATING = "repeating"


class RecordField(StrEnum):
    """Fields on a record. CLOSED vocabulary.

    Each field's `Value` type is fixed and self-describing, so the bridge never needs a
    separate storage-kind tag:
        STATUS           -> State
        PROGRESS         -> Progress
        RATING           -> Rating
        STARTED_AT       -> date or UTC datetime
        FINISHED_AT      -> date or UTC datetime
        LAST_ACTIVITY_AT -> datetime (UTC)
        REPEAT_COUNT     -> int
        NOTES            -> str
    """

    STATUS = "status"
    PROGRESS = "progress"
    RATING = "rating"
    STARTED_AT = "started_at"
    FINISHED_AT = "finished_at"
    LAST_ACTIVITY_AT = "last_activity_at"
    REPEAT_COUNT = "repeat_count"
    NOTES = "notes"


class TemporalPrecision(StrEnum):
    """Temporal precision advertised for a temporal field or event constraint."""

    DATE = "date"
    DATETIME = "datetime"


@dataclass(frozen=True, slots=True)
class TemporalConstraint:
    """Accepted temporal granularity."""

    precision: TemporalPrecision


@dataclass(frozen=True, slots=True)
class NumericConstraint:
    """Accepted numeric range and quantization for an int/float field.

    `step` is measured from `minimum` when present, else from 0.
    """

    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None

    def __post_init__(self) -> None:
        """Validate numeric constraint invariants."""
        if self.step is not None and self.step <= 0:
            raise ValueError("NumericConstraint.step must be > 0")
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise ValueError(
                "NumericConstraint.minimum must be <= NumericConstraint.maximum"
            )


@dataclass(frozen=True, slots=True)
class TextConstraint:
    """Accepted textual limits for a string field."""

    max_length: int | None = None

    def __post_init__(self) -> None:
        """Validate text constraint invariants."""
        if self.max_length is not None and self.max_length < 0:
            raise ValueError("TextConstraint.max_length must be >= 0")


@dataclass(frozen=True, slots=True)
class ProgressConstraint:
    """Which `Progress` dimensions are writable/comparable user state.

    `Progress.current` is always the synced value for `RecordField.PROGRESS`. Set
    `current` when the provider only accepts a bounded or quantized progress value.
    Progress quantization floors partial units because progress counts completed units.
    Set `total` or `unit` to false when the provider owns those dimensions as media
    metadata rather than writable progress state.
    """

    current: NumericConstraint | None = None
    total: bool = True
    unit: bool = True


type FieldConstraint = (
    TemporalConstraint | NumericConstraint | TextConstraint | ProgressConstraint
)


class FacetName(StrEnum):
    """Selectively hydratable facets on a node."""

    TITLES = "titles"
    ARTWORK = "artwork"
    IDS = "ids"
    STRUCTURE = "structure"
    METADATA = "metadata"


class ChangeKind(StrEnum):
    """Which model an incremental change touched."""

    NODE = "node"
    RECORD = "record"
    EVENT = "event"


class ChangeAction(StrEnum):
    """How the changed object moved."""

    UPSERTED = "upserted"
    DELETED = "deleted"
    UNKNOWN = "unknown"


class WriteOp(StrEnum):
    """Write operations a provider may advertise."""

    UPSERT_RECORD = "upsert_record"
    DELETE_RECORD = "delete_record"
    APPEND_EVENT = "append_event"


class WriteError(StrEnum):
    """Machine-readable reason a write failed, so the planner can pick a policy.

    `WriteResult.error` carries the human detail.
    """

    UNSUPPORTED = "unsupported"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    DUPLICATE = "duplicate"
    INVALID = "invalid"
    AUTH = "auth"
    RATE_LIMITED = "rate_limited"
    TRANSIENT = "transient"
    INTERNAL = "internal"


class NodeKind(StrEnum):
    """Semantic node kind used for cross-provider classification.

    For display, like-with-like grouping, and choosing the coordinate interpretation.
    Operational sync semantics live in `NodeFlag`. A provider maps its natives onto
    these in `Capabilities.nodes`.
    """

    SERIES = "series"
    SEASON = "season"
    EPISODE = "episode"
    FILM = "film"
    BOOK_SERIES = "book_series"
    BOOK = "book"
    CHAPTER = "chapter"
    GAME = "game"


class EventKind(StrEnum):
    """Semantic event channel kind.

    `SCROBBLE` is a completed consumption occurrence, regardless of whether the native
    provider calls it a play, read, listen, or game session. `CHECKIN` is a temporary or
    real-time declaration that the user is consuming something now. `PROGRESS` captures
    point-in-time resume or playback position updates without implying completion.
    """

    SCROBBLE = "scrobble"
    CHECKIN = "checkin"
    PROGRESS = "progress"
    RATING = "rating"
    REVIEW = "review"
    COLLECTION = "collection"
    WATCHLIST = "watchlist"


type Semantic = NodeKind | EventKind | Status


@dataclass(frozen=True, slots=True)
class Descriptor[S: Semantic]:
    """A native vocabulary value mapped onto a closed shared semantic.

    `native` is the provider's exact term. `semantic` is the closed cross-provider
    meaning the bridge matches on. `semantic is None` marks the native as provider-
    private: used only for display or provider-local round trips.
    """

    native: str
    semantic: S | None = None
    description: str | None = None


@dataclass(frozen=True, slots=True)
class ExternalId:
    """A stable external identity used for cross-provider matching.

    In-memory form of an anibridge-mappings descriptor whose wire format is
    `authority:value[:scope]`.
    """

    authority: str
    value: str
    scope: str | None = None

    @classmethod
    def parse(cls, descriptor: str) -> ExternalId:
        """Parse an `authority:value[:scope]` descriptor."""
        parts = descriptor.split(":")
        if len(parts) == 2:
            authority, value = parts
            return cls(authority, value)
        if len(parts) == 3:
            authority, value, scope = parts
            return cls(authority, value, scope)
        raise ValueError(f"not a valid descriptor: {descriptor!r}")

    @property
    def descriptor(self) -> str:
        """Render back to the `authority:value[:scope]` wire format."""
        if self.scope is None:
            return f"{self.authority}:{self.value}"
        return f"{self.authority}:{self.value}:{self.scope}"

    def __repr__(self) -> str:
        """Debug-friendly descriptor form."""
        return self.descriptor


@dataclass(frozen=True, slots=True)
class Step:
    """One coordinate on the path into an anchor's part space."""

    axis: str
    value: int | str


@dataclass(frozen=True, slots=True)
class Ref:
    """Addresses an anchor, or a part within it via `path`.

    `key` is the provider's identifier for the anchor. An empty `path` points at the
    anchor; a non-empty path points at a coordinate inside it. The same `(anchor, path)`
    aligns across providers even when one materializes the part as its own object and
    another does not.
    """

    key: str
    path: tuple[Step, ...] = ()

    @classmethod
    def anchor(cls, key: str) -> Ref:
        """Reference the anchor itself."""
        return cls(key)

    @classmethod
    def at(cls, key: str, *steps: tuple[str, int | str]) -> Ref:
        """Reference a part: `Ref.at(show, ("season", 1), ("episode", 3))`."""
        return cls(key, tuple(Step(axis, value) for axis, value in steps))

    @property
    def is_anchor(self) -> bool:
        """Whether this ref points at the anchor rather than a part."""
        return not self.path

    def child(self, axis: str, value: int | str) -> Ref:
        """Extend this ref one coordinate deeper."""
        return Ref(self.key, (*self.path, Step(axis, value)))

    def __repr__(self) -> str:
        """Debug-friendly string form showing the key and path."""
        path_str = ",".join(f"{step.axis}={step.value}" for step in self.path)
        return f"{self.key}:{path_str}" if path_str else str(self.key)


@dataclass(frozen=True, slots=True)
class Match:
    """Resolution of one external id onto a provider ref.

    Resolution is not positional: `resolve` may return zero matches for an unknown id or
    several for an ambiguous one, so every `Match` echoes the `external_id` it resolves.
    `confidence`, when set, ranks ambiguous matches (0.0-1.0); `None` means the provider
    does not score matches.
    """

    external_id: ExternalId
    ref: Ref
    confidence: float | None = None

    def __post_init__(self) -> None:
        """Validate match invariants."""
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("Match.confidence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class Titles:
    """TITLES facet."""

    primary: str
    alternates: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Artwork:
    """ARTWORK facet."""

    images: Mapping[str, str] = field(default_factory=dict)

    @property
    def poster(self) -> str | None:
        """Convenience accessor for the conventional 'poster' role."""
        return self.images.get("poster")


@dataclass(frozen=True, slots=True)
class Identifiers:
    """IDS facet: the external identities of this node."""

    ids: tuple[ExternalId, ...] = ()


@dataclass(frozen=True, slots=True)
class Part:
    """One addressable position inside an anchor's coordinate space.

    `key` is present only when the provider materializes the part as its own object
    (e.g. a Plex episode). It is absent for synthetic positions (e.g. an AniList episode
    index that exists only as a progress coordinate).

    `title` is a lightweight inline label only.
    """

    position: tuple[Step, ...]
    title: str | None = None
    key: str | None = None


@dataclass(frozen=True, slots=True)
class Structure:
    """STRUCTURE facet: the coordinate space of an anchor.

    `axes` is the ordered axis vocabulary (e.g. `("season", "episode")` or
    `("chapter",)`). `parts` enumerates valid positions; it is how the bridge learns to
    expand/collapse aggregate state against granular activity.
    """

    axes: tuple[str, ...] = ()
    parts: tuple[Part, ...] = ()


@dataclass(frozen=True, slots=True)
class Metadata:
    """METADATA facet: opaque provider-neutral key/value pairs.

    Presentation-only, never synchronized.
    """

    values: Mapping[str, MetaValue] = field(default_factory=dict)


type Facet = Titles | Artwork | Identifiers | Structure | Metadata


@dataclass(frozen=True, slots=True)
class Node:
    """A catalog entity: an anchor or materialized part.

    `title` and `url` are inexpensive labels that may always be returned. `facets`
    contains only the requested hydrated facets. An absent facet means "not hydrated",
    not "empty".
    """

    ref: Ref
    kind: str
    title: str | None = None
    url: str | None = None
    labels: tuple[str, ...] = ()
    flags: frozenset[NodeFlag] = field(default_factory=frozenset)
    facets: Mapping[FacetName, Facet] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class State:
    """A lifecycle state: native label plus normalized status."""

    native: str | None = None
    status: Status | None = None

    def __post_init__(self) -> None:
        """Reject state values with no comparable meaning."""
        if self.native is None and self.status is None:
            raise ValueError("State must include native, status, or both")


@dataclass(frozen=True, slots=True)
class Progress:
    """A progress channel.

    `current` is the comparable user-state value. `total` and `unit` describe the shape
    of that channel and may be omitted when the provider derives them from catalog data.
    `unit` is provider-native and open-ended, such as "episode", "page", or "minute".
    """

    current: int | float | None
    total: int | float | None = None
    unit: str | None = None

    def __post_init__(self) -> None:
        """Validate progress invariants."""
        if self.current is not None and self.current < 0:
            raise ValueError("Progress.current must be >= 0")
        if self.total is not None and self.total < 0:
            raise ValueError("Progress.total must be >= 0")


@dataclass(frozen=True, slots=True)
class Rating:
    """A rating with its native scale (e.g. 4.5 on a scale of 5)."""

    value: float
    scale: tuple[float, float, float]

    def __post_init__(self) -> None:
        """Validate rating invariants."""
        minimum, maximum, step = self.scale
        if minimum > maximum:
            raise ValueError("Rating.scale minimum must be <= maximum")
        if step <= 0:
            raise ValueError("Rating.scale step must be > 0")
        if not minimum <= self.value <= maximum:
            raise ValueError("Rating.value must be within Rating.scale")


type Value = State | Progress | Rating | Scalar | date | datetime


@dataclass(frozen=True, slots=True)
class RecordUnit:
    """Per-source-unit state that contributes to an aggregate `Record`.

    `index` is the one-based ordinal in the record's source unit space. For a
    season-level episode record, this is the episode number. For a chapter progress
    record, this is the chapter number. AniMap ranges address these indexes directly,
    so planners can project mapped ranges without borrowing values from unrelated units.
    """

    index: int
    key: str | None = None
    values: Mapping[RecordField, Value] = field(default_factory=dict)
    metadata: Mapping[str, MetaValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate unit invariants."""
        if self.index < 1:
            raise ValueError("RecordUnit.index must be >= 1")
        _validate_record_values(self.values)


@dataclass(frozen=True, slots=True)
class Record:
    """Current aggregate user state about a ref.

    `surface` is an opaque provider-local dispatch handle advertised by `RecordSpec`.
    It identifies which native state surface produced the record and which provider
    write path should receive updates. It must be stable within one provider, but it
    does not need to match another provider's name for the same concept. AniBridge
    decides cross-provider compatibility from `RecordSpec.fields`, not from the
    surface string. `key` is a provider record id when the provider has one.
    `updated_at` is the mutation time for this aggregate state, not the time of the
    underlying activity being represented.

    In `values`, an absent `RecordField` means "unknown" or "unset". Never store an
    explicit `None`; use `UpsertRecord.clear` to remove fields.

    `units` carries source-unit values behind the aggregate. It is not written to target
    providers directly; the planner uses it to project mapped ranges without borrowing
    fields from unrelated units in the same aggregate record.
    """

    ref: Ref
    surface: str
    key: str | None = None
    url: str | None = None
    updated_at: datetime | None = None
    revision: str | None = None
    ids: tuple[ExternalId, ...] = ()
    values: Mapping[RecordField, Value] = field(default_factory=dict)
    units: tuple[RecordUnit, ...] = ()
    metadata: Mapping[str, MetaValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate record invariants."""
        if not self.surface:
            raise ValueError("Record.surface must name a record surface")
        _validate_utc(self.updated_at, "Record.updated_at")
        _validate_record_values(self.values)
        unit_indexes = [unit.index for unit in self.units]
        if len(set(unit_indexes)) != len(unit_indexes):
            raise ValueError("Record.units indexes must be unique")


@dataclass(frozen=True, slots=True)
class Event:
    """An immutable timestamped user activity occurrence.

    `kind` names a provider-native activity channel advertised by `EventSpec`. `at` is
    when the activity occurred and must be timezone-aware UTC. `key`, when present, is a
    stable provider event id. `dedupe_key`, when present, is a stable idempotency
    signature for append retries and event-to-event replication.
    """

    ref: Ref
    kind: str
    at: datetime
    key: str | None = None
    dedupe_key: str | None = None
    recorded_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: Mapping[str, MetaValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate event invariants."""
        if not self.kind:
            raise ValueError("Event.kind must name an event channel")
        _validate_utc(self.at, "Event.at")
        _validate_utc(self.recorded_at, "Event.recorded_at")
        _validate_utc(self.updated_at, "Event.updated_at")


@dataclass(frozen=True, slots=True)
class BackupArtifact:
    """Provider-managed backup payload for AniBridge to persist.

    `content` is the exact provider payload to write to disk. `file_extension` must
    include the leading dot, such as `.json` or `.zip`.
    """

    content: bytes
    file_extension: str = ".json"
    media_type: str | None = None

    def __post_init__(self) -> None:
        """Validate backup artifact invariants."""
        if not self.file_extension.startswith("."):
            raise ValueError("BackupArtifact.file_extension must start with '.'")


@dataclass(frozen=True, slots=True)
class Page[ItemT]:
    """One page of results with an opaque continuation cursor.

    `total`, when known, is the total number of items matching the query across all
    pages. Providers may leave it unset when calculating a total would require extra
    work or the remote API does not expose one.
    """

    items: tuple[ItemT, ...]
    cursor: str | None = None
    total: int | None = None


@dataclass(frozen=True, slots=True)
class ScanItem:
    """A catalog node paired with optional aggregate state.

    Scans are for discovery. They may include aggregate records when the provider can
    fetch those cheaply, but exact event replication uses `fetch_events` after planning
    from the scan result.
    """

    node: Node
    records: tuple[Record, ...] = ()


@dataclass(frozen=True, slots=True)
class NodeQuery:
    """Targeted node lookup.

    Only requested `facets` are hydrated. `native_node_kinds` filters on the provider's
    own open-string kinds, not the closed semantic `NodeKind`.
    """

    refs: tuple[Ref, ...] = ()
    keys: tuple[str, ...] = ()
    native_node_kinds: tuple[str, ...] = ()
    flags: frozenset[NodeFlag] = field(default_factory=frozenset)
    facets: frozenset[FacetName] = field(default_factory=frozenset)
    cursor: str | None = None
    limit: int | None = None


@dataclass(frozen=True, slots=True)
class RecordQuery:
    """Selective record lookup.

    Only requested `fields` are hydrated. `record_surfaces` filters on opaque
    provider-local record surfaces.
    """

    refs: tuple[Ref, ...] = ()
    keys: tuple[str, ...] = ()
    record_surfaces: tuple[str, ...] = ()
    fields: frozenset[RecordField] = field(default_factory=frozenset)
    changed_after: datetime | None = None
    cursor: str | None = None
    limit: int | None = None

    def __post_init__(self) -> None:
        """Validate record query invariants."""
        _validate_utc(self.changed_after, "RecordQuery.changed_after")


@dataclass(frozen=True, slots=True)
class EventQuery:
    """Detailed event lookup.

    `native_event_kinds` filters on the provider's own open-string activity channels.
    `start_at` is inclusive and `end_at` is exclusive. `with_metadata` controls only
    opaque metadata hydration; event identity and timestamps are always returned.
    """

    refs: tuple[Ref, ...] = ()
    keys: tuple[str, ...] = ()
    native_event_kinds: tuple[str, ...] = ()
    start_at: datetime | None = None
    end_at: datetime | None = None
    changed_after: datetime | None = None
    with_metadata: bool = False
    cursor: str | None = None
    limit: int | None = None

    def __post_init__(self) -> None:
        """Validate event query invariants."""
        _validate_utc(self.start_at, "EventQuery.start_at")
        _validate_utc(self.end_at, "EventQuery.end_at")
        _validate_utc(self.changed_after, "EventQuery.changed_after")
        if (
            self.start_at is not None
            and self.end_at is not None
            and self.start_at > self.end_at
        ):
            raise ValueError("EventQuery.start_at must be <= end_at")


@dataclass(frozen=True, slots=True)
class ScanQuery:
    """Source enumeration.

    `ScanQuery` is separate from targeted node/record/event queries. It discovers nodes
    and may attach cheap record state. `native_*_kinds` filters use the provider's own
    open-string node/event kinds; `record_surfaces` filters record dispatch surfaces.
    """

    sources: tuple[Ref, ...] = ()
    native_node_kinds: tuple[str, ...] = ()
    flags: frozenset[NodeFlag] = field(default_factory=frozenset)
    facets: frozenset[FacetName] = field(default_factory=frozenset)
    record_surfaces: frozenset[str] = field(default_factory=frozenset)
    record_fields: frozenset[RecordField] = field(default_factory=frozenset)
    include_records: bool = True
    require_user_data: bool = False
    cursor: str | None = None
    limit: int | None = None


@dataclass(frozen=True, slots=True)
class ChangeQuery:
    """Incremental change-feed poll.

    `cursor` is provider-owned and should be preferred when available. `changed_after`
    is a fallback for providers with timestamp polling. `kinds` filters the model type
    of changes requested.
    """

    cursor: str | None = None
    changed_after: datetime | None = None
    kinds: frozenset[ChangeKind] = field(default_factory=frozenset)
    limit: int | None = None

    def __post_init__(self) -> None:
        """Validate change query invariants."""
        _validate_utc(self.changed_after, "ChangeQuery.changed_after")


@dataclass(frozen=True, slots=True)
class UpsertRecord:
    """Create or patch a record.

    `set` applies field values, and `clear` removes fields. `token` is an opaque
    client-side correlation tag echoed on the matching `WriteResult`.
    `expected_revision`, when given, requests optimistic-concurrency checking.
    """

    ref: Ref
    surface: str
    key: str | None = None
    token: str | None = None
    expected_revision: str | None = None
    set: Mapping[RecordField, Value] = field(default_factory=dict)
    clear: frozenset[RecordField] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        """Validate upsert invariants."""
        if not self.surface:
            raise ValueError("UpsertRecord.surface must name a record surface")
        _validate_record_values(self.set)
        overlap = set(self.set).intersection(self.clear)
        if overlap:
            raise ValueError(f"fields cannot be both set and cleared: {overlap!r}")


@dataclass(frozen=True, slots=True)
class DeleteRecord:
    """Delete a record by key, or by `(ref, surface)`."""

    ref: Ref | None = None
    surface: str | None = None
    key: str | None = None
    token: str | None = None

    def __post_init__(self) -> None:
        """Validate delete-record invariants."""
        if self.key is None and (self.ref is None or not self.surface):
            raise ValueError("DeleteRecord requires key or both ref and surface")


type RecordWrite = UpsertRecord | DeleteRecord


@dataclass(frozen=True, slots=True)
class AppendEvent:
    """Append one activity event.

    `at` must be timezone-aware UTC. `dedupe_key`, when present, is a provider-neutral
    idempotency signature chosen by AniBridge. Providers that advertise idempotent
    appends must treat repeated writes with the same dedupe key as the same event.
    """

    ref: Ref
    kind: str
    at: datetime
    token: str | None = None
    dedupe_key: str | None = None
    metadata: Mapping[str, MetaValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate append-event invariants."""
        if not self.kind:
            raise ValueError("AppendEvent.kind must name an event channel")
        _validate_utc(self.at, "AppendEvent.at")


type EventWrite = AppendEvent


@dataclass(frozen=True, slots=True)
class WriteResult:
    """Outcome of one write, returned positionally with its input.

    `token` echoes the request's correlation tag for extra safety. On failure, `code` is
    the machine-readable reason that drives retry, skip, or abort behavior, and `error`
    is optional human-readable detail.
    """

    ok: bool
    op: WriteOp
    token: str | None = None
    key: str | None = None
    ref: Ref | None = None
    revision: str | None = None
    code: WriteError | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        """Validate write-result invariants."""
        if self.ok and (self.code is not None or self.error is not None):
            raise ValueError("successful WriteResult must not include code or error")
        if not self.ok and self.code is None:
            raise ValueError("failed WriteResult must include code")


@dataclass(frozen=True, slots=True)
class NodeChange:
    """A catalog change.

    `facets` names what changed for targeted rehydration. Empty `facets` means the
    changed facets are unknown and the node should be reread fully.
    """

    action: ChangeAction = ChangeAction.UNKNOWN
    ref: Ref | None = None
    key: str | None = None
    at: datetime | None = None
    facets: frozenset[FacetName] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        """Validate node-change invariants."""
        _validate_utc(self.at, "NodeChange.at")


@dataclass(frozen=True, slots=True)
class RecordChange:
    """A record change.

    `surface` is the affected record surface. `fields` names what changed for targeted
    rehydration. Empty `fields` means the changed fields are unknown and the record
    should be reread fully.
    """

    action: ChangeAction = ChangeAction.UNKNOWN
    ref: Ref | None = None
    key: str | None = None
    surface: str | None = None
    at: datetime | None = None
    fields: frozenset[RecordField] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        """Validate record-change invariants."""
        _validate_utc(self.at, "RecordChange.at")


@dataclass(frozen=True, slots=True)
class EventChange:
    """An event change.

    Event changes refer to immutable activity occurrences. Providers that only expose a
    broad activity invalidation may omit `key`, `ref`, and `at`, but should include the
    affected `kind` when known.
    """

    action: ChangeAction = ChangeAction.UNKNOWN
    ref: Ref | None = None
    key: str | None = None
    dedupe_key: str | None = None
    kind: str | None = None
    at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate event-change invariants."""
        _validate_utc(self.at, "EventChange.at")


type Change = NodeChange | RecordChange | EventChange


@dataclass(frozen=True, slots=True)
class InboundRequest:
    """A framework-agnostic push payload (webhook or similar)."""

    method: str
    path: str
    headers: Mapping[str, str] = field(default_factory=dict)
    query: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    body: bytes = b""


@dataclass(frozen=True, slots=True)
class InboundResult:
    """Parsed inbound changes.

    `matched` is False when the payload does not target this provider.
    """

    matched: bool
    changes: tuple[Change, ...] = ()
    cursor: str | None = None


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """The contract for one planner-visible record field.

    The value shape is fixed by `RecordField`, so it is not restated here. `constraints`
    declares the provider's native limits for this field, such as date-only datetimes,
    whole-number rating scales, or maximum note length. `values` declares representable
    status semantics for the `STATUS` field and the native status value a provider uses
    for each semantic. Native values may repeat when a provider distinguishes statuses
    through side-channel fields.
    """

    field: RecordField
    readable: bool = True
    writable: bool = False
    constraints: tuple[FieldConstraint, ...] = ()
    values: tuple[Descriptor[Status], ...] = ()
    description: str | None = None

    def __post_init__(self) -> None:
        """Reject ambiguous field capability declarations."""
        if self.field != RecordField.STATUS and self.values:
            raise ValueError("FieldSpec.values is only valid for RecordField.STATUS")
        if self.field == RecordField.STATUS and (self.readable or self.writable):
            if not self.values:
                raise ValueError("STATUS fields must declare supported native values")
            _validate_status_values(self.values, writable=self.writable)
        _validate_field_constraints(self.field, self.constraints)


@dataclass(frozen=True, slots=True)
class NodeSpec:
    """Capability declaration for one native node kind."""

    kind: Descriptor[NodeKind]
    flags: frozenset[NodeFlag] = field(default_factory=frozenset)
    coordinate_axes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RecordSpec:
    """Capability declaration for one provider-local aggregate-state surface.

    `surface` is an opaque provider dispatch handle used in `Record.surface`. It names
    one provider-local aggregate-state surface: for example a media-list entry API, an
    anime-list entry API, or a user-state table. Use multiple surfaces only when the
    provider has distinct native record stores or write paths with different field
    capabilities. AniBridge matches record surfaces by compatible field capabilities,
    not by surface names. `write_ops` must only contain record operations.
    """

    surface: str = "default"
    fields: Mapping[RecordField, FieldSpec] = field(default_factory=dict)
    write_ops: frozenset[WriteOp] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        """Validate record surface declarations."""
        if not self.surface:
            raise ValueError("RecordSpec.surface must name a record surface")
        invalid = self.write_ops.difference(
            {WriteOp.UPSERT_RECORD, WriteOp.DELETE_RECORD}
        )
        if invalid:
            raise ValueError(
                f"RecordSpec.write_ops contains event operations: {invalid}"
            )
        for field_name, spec in self.fields.items():
            if field_name != spec.field:
                raise ValueError("RecordSpec.fields keys must match FieldSpec.field")


@dataclass(frozen=True, slots=True)
class EventSpec:
    """Capability declaration for one native activity channel.

    `kind.native` is the string used in `Event.kind`. `idempotent_appends` says whether
    repeated appends with the same `AppendEvent.dedupe_key` avoid duplicate events.
    """

    kind: Descriptor[EventKind]
    write_ops: frozenset[WriteOp] = field(default_factory=frozenset)
    temporal: TemporalConstraint = field(
        default_factory=lambda: TemporalConstraint(TemporalPrecision.DATETIME)
    )
    idempotent_appends: bool = False

    def __post_init__(self) -> None:
        """Validate event channel declarations."""
        invalid = self.write_ops.difference({WriteOp.APPEND_EVENT})
        if invalid:
            raise ValueError(
                f"EventSpec.write_ops contains record operations: {invalid}"
            )


@dataclass(frozen=True, slots=True)
class Capabilities:
    """Provider vocabularies and sub-method granularity.

    Method presence is answered by `isinstance(provider, SupportsX)`. `Capabilities`
    describes what those methods support.

    `nodes` and `events` map native channel/kind strings onto closed semantics.
    `records` advertise provider-native channels and field capabilities.
    `external_authorities` holds AniMap descriptor authority tokens this provider can
    emit or resolve. These are mapping-database identifiers, not provider namespaces:
    `Provider.NAMESPACE` identifies the AniBridge plugin/provider implementation.
    """

    roles: frozenset[Role] = field(default_factory=frozenset)
    facets: frozenset[FacetName] = field(default_factory=frozenset)
    nodes: tuple[NodeSpec, ...] = ()
    records: tuple[RecordSpec, ...] = ()
    events: tuple[EventSpec, ...] = ()
    change_kinds: frozenset[ChangeKind] = field(default_factory=frozenset)
    external_authorities: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class Account:
    """The authenticated account a provider instance is bound to."""

    key: str
    title: str
    url: str | None = None


class Provider(ABC):
    """Base for all AniBridge providers.

    A provider instance is bound to a single authenticated account. Mix in each
    `SupportsX` interface the provider can fulfill, and advertise roles and
    vocabularies through `capabilities()`.
    """

    DISPLAY_NAME: ClassVar[str]
    NAMESPACE: ClassVar[str]

    def __init__(
        self,
        *,
        logger: Logger,
        config: Mapping[str, object] | None = None,
    ) -> None:
        """Bind a provider instance to a logger and optional config mapping."""
        self.log = logger
        self.config = dict(config or {})

    async def initialize(self) -> None:
        """Run async setup after construction."""
        return

    async def clear_cache(self) -> None:
        """Drop provider-managed caches."""
        return

    async def close(self) -> None:
        """Release provider resources."""
        return

    @abstractmethod
    def account(self) -> Account | None:
        """Return the authenticated account, or None before `initialize`."""

    def capabilities(self) -> Capabilities:
        """Advertise vocabularies and sub-method granularity."""
        return Capabilities()


class SupportsNodeReads(ABC):
    """Targeted node reads by ref or other node-query filters."""

    @abstractmethod
    async def fetch_nodes(self, query: NodeQuery) -> Page[Node]:
        """Fetch nodes matching the requested query projection."""


class SupportsNodeSearch(ABC):
    """Provider catalog search by user-entered text."""

    @abstractmethod
    async def search_nodes(
        self,
        query: str,
        *,
        limit: int = 10,
        facets: frozenset[FacetName] = frozenset(),
    ) -> Page[Node]:
        """Search provider catalog nodes matching the requested text."""


class SupportsScan(ABC):
    """Source enumeration for discovery."""

    @abstractmethod
    async def scan(self, query: ScanQuery) -> Page[ScanItem]:
        """Scan provider content in bulk."""


class SupportsMapping(ABC):
    """Resolve external ids onto this provider's own refs.

    This is per-provider identity only: `resolve` turns a descriptor identity into a
    native ref, and the `IDS` facet does the reverse. Cross-provider directional
    translation between authorities, including ranges and ratios, is performed by
    AniBridge's mapping layer over the anibridge-mappings dataset, not by providers.
    """

    @abstractmethod
    async def resolve(self, ids: Sequence[ExternalId]) -> Sequence[Match]:
        """Resolve external identities onto this provider's refs."""


class SupportsRecordReads(ABC):
    """Selective aggregate-state reads."""

    @abstractmethod
    async def fetch_records(self, query: RecordQuery) -> Page[Record]:
        """Fetch records matching the requested field projection."""


class SupportsRecordWrites(ABC):
    """Record mutations. Granularity is advertised in `RecordSpec.write_ops`.

    Results are positional and independent. Providers may optimize multiple writes
    internally, but should not expose partial batch ambiguity: when one write fails,
    return a failed `WriteResult` for that write instead of raising after applying an
    unknown subset.
    """

    @abstractmethod
    async def write_records(
        self, writes: Sequence[RecordWrite]
    ) -> Sequence[WriteResult]:
        """Apply record writes and return one result per input."""


class SupportsEventReads(ABC):
    """Detailed immutable activity reads."""

    @abstractmethod
    async def fetch_events(self, query: EventQuery) -> Page[Event]:
        """Fetch detailed events matching the query."""


class SupportsEventWrites(ABC):
    """Event mutations. Granularity is advertised in `EventSpec.write_ops`."""

    @abstractmethod
    async def write_events(self, writes: Sequence[EventWrite]) -> Sequence[WriteResult]:
        """Apply event writes and return one result per input."""


class SupportsChangeFeed(ABC):
    """Poll incremental changes."""

    @abstractmethod
    async def poll_changes(self, query: ChangeQuery) -> Page[Change]:
        """Poll the provider's incremental change feed."""


class SupportsBackupExports(ABC):
    """Export provider-managed backup payloads for AniBridge to persist."""

    @abstractmethod
    async def export_backup(self) -> BackupArtifact | None:
        """Return a provider-managed backup payload, if supported."""


class SupportsBackupImports(ABC):
    """Import provider-managed backup payloads persisted by AniBridge."""

    @abstractmethod
    async def import_backup(self, payload: bytes) -> None:
        """Restore provider-managed state from a backup payload."""


class SupportsInboundChanges(ABC):
    """Parse push-style change notifications."""

    @abstractmethod
    async def parse_inbound(self, request: InboundRequest) -> InboundResult:
        """Parse an inbound push payload into normalized changes."""
