"""Provider contracts for AniBridge provider authors.

This module defines the interface between AniBridge and a concrete media provider (e.g.
Plex, AniList, Trakt, ...).

When implementing a provider, your job is to translate the provider's native objects,
identifiers, lists, activity, and constraints into the normalized objects in this
module. The contract is intentionally flexible so providers can keep their native shape,
but the values you return must have precise semantics. AniBridge relies on those
semantics to match media, compare state, plan writes, avoid duplicate work, and preserve
provider-specific details where appropriate.

----------------------------------------------------------------------------------------
Implementation guide
----------------------------------------------------------------------------------------

1. Start with identity: anchors, refs, and paths

    The mappable unit is an anchor (a show, movie, manga, game, or similar media). A
    `Ref` addresses that anchor by `key`. A `Ref` may also include a `path` of `Step`s
    into the anchor's part space, such as season/episode/chapter.

    Use the same anchor key for every coordinate inside the same work. Add path steps
    when the provider exposes or accepts state below the anchor level.

    This lets AniBridge align providers that model parts differently. For example, one
    provider may expose distinct episode objects, while another only exposes an
    aggregate "12 episodes watched". Both still describe the same anchor plus coordinate
    space.

2. Advertise native vocabularies through capabilities

    Provider-native names are open strings. Use them in `Node.kind`, `Record.kind`,
    `Event.kind`, `Step.axis`, `Progress.unit`, and artwork roles.

    Closed enums are the values AniBridge reasons over: `Status`, `RecordField`,
    `NodeFlag`, `FacetName`, `ChangeKind`, `WriteOp`, `TemporalPrecision`, `WriteError`
    and the semantic kind enums `NodeKind`, `RecordKind`, and `EventKind`.

    In `capabilities()`, map each native kind to a closed semantic with a `Descriptor`.
    AniBridge never compares native strings across providers. It maps source-native
    values to semantics, chooses compatible target-native values for those semantics,
    and translates from there.

    Use `semantic=None` for native values that should be kept for display or round-trip
    fidelity, but never used for cross-provider sync.

3. Put operational node meaning in flags

    `NodeKind` describes what a node is for display, grouping, and coordinate
    interpretation. `NodeFlag` describes how AniBridge may operate on that node.

    A provider should attach flags based on the behavior the node supports:

    `ANCHOR`: the root work-level node AniBridge maps across providers, such as a show,
    movie, manga, book series, or game.

    `CONTAINER`: a node that can expand into addressable children or parts, such as a
    show with seasons, a season with episodes, or a book series with volumes.

    `CONSUMABLE`: a leaf a user can complete, such as an episode, movie, chapter, track,
    or other playable/readable unit.

    `TRACKABLE`: a ref that can hold user state, such as progress, status, rating,
    dates, repeat count, notes, or activity.

    `ORDERED_PARTS`: a node whose part coordinates have meaningful order, such as
    episode number, chapter number, disc/track order, or similar progress positions.

    `SCAN_ROOT`: a node that is valid as a starting point for bulk enumeration through
    `scan`.

    A node may have multiple flags. For example, a TV series is often both an `ANCHOR`
    and a `CONTAINER`, while an episode is often both `CONSUMABLE` and `TRACKABLE`.

4. Choose the user-state shape your provider actually owns

    Return `Record` for current aggregate state about a ref, such as status, progress,
    rating, dates, repeat count, or notes.

    Return `Event` for immutable timestamped activity, such as a play, scrobble, read,
    or check-in.

    Return `EventSummary` when the provider can expose aggregate event counts without
    paging the full event stream.

    Do not emit both per-part `Record`s and `Event`s for the identical fact unless the
    provider materially exposes both views.

5. Hydrate only the requested projection

    `Node.title`, `Node.url`, and `Part.title` should be cheap labels that are always
    safe to return.

    Facets such as `TITLES`, `ARTWORK`, `IDS`, `STRUCTURE`, and `METADATA` are hydrated
    only when requested. Record fields follow the same rule through the requested
    `RecordField` set.

    Returned objects are frozen value objects, not lazy proxies. Attribute access must
    never perform I/O. To load more data, query the same `Ref` again with a wider facet
    or field projection, preferably batched across many refs.

    Create a separate facet only when the data requires a separate fetch, a large
    payload, or a distinct provider endpoint.

6. Keep metadata opaque

    Every `metadata: Mapping[str, MetaValue]` is provider passthrough. AniBridge does
    not plan from it, compare it, or translate it. Metadata is only for display/logging.

    If the bridge must understand a value, model it as a normalized field, facet, flag,
    descriptor, or constraint instead of putting it in metadata.

7. Normalize temporal values and constraints

    Every datetime crossing this contract must be timezone-aware UTC. A naive datetime
    is a contract violation. Date-precision values should be represented as `date`,
    not as artificial midnight datetimes.

    If a provider only supports date-level precision, advertise that with
    `TemporalConstraint(precision=TemporalPrecision.DATE)` in the relevant
    `FieldSpec.constraints`.

    Use field constraints to describe what the provider can represent or accept:
    date-vs-datetime precision, numeric range and step, text length, progress shape,
    and similar limits. Temporal constraints also tell the bridge how to translate
    between date and datetime providers.

    For `RecordField.PROGRESS`, `Progress.current` is the synced user-state value.
    Providers with bounded or discrete progress counts should describe that current
    value with `ProgressConstraint(current=NumericConstraint(...))`.
    `Progress.total` and `Progress.unit` describe the shape of that progress channel.
    Providers that derive total/unit from media metadata instead of user state should
    advertise that with `ProgressConstraint(total=False, unit=False)`.

8. Separate method presence from method granularity

    Add `SupportsX` mixins for the methods your provider implements. For example, use
    `SupportsScan` for bulk enumeration, `SupportsRecordReads` for record reads, and
    `SupportsRecordWrites` for record writes.

    Use `capabilities()` to describe what those methods can actually do: roles, facets,
    native kind mappings, coordinate axes, record fields, event kinds, write operations,
    change kinds, and external authorities. `isinstance(provider, SupportsX)` says a
    method exists, but `capabilities()` says what the method supports.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
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
    "ChangeKind",
    "ChangeQuery",
    "DeleteEvent",
    "DeleteRecord",
    "Descriptor",
    "Event",
    "EventChange",
    "EventKind",
    "EventQuery",
    "EventSummary",
    "EventSummaryQuery",
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
    "RecordKind",
    "RecordQuery",
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
    "SupportsEventSummaries",
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

# Record values may contain only non-null scalars. A missing `RecordField` represents
# "unset", so `None` must not appear as a record value.
type Scalar = str | int | float | bool
type ScalarValue = Scalar | None
type MetaValue = ScalarValue | tuple[ScalarValue, ...]


class Role(StrEnum):
    """Direction a provider may serve in a sync."""

    SOURCE = "source"
    TARGET = "target"


class NodeFlag(StrEnum):
    """Operational semantics the sync engine needs, attached to a catalog node."""

    ANCHOR = "anchor"  # mappable unit; carries cross-provider identity
    CONTAINER = "container"  # has addressable children/parts
    CONSUMABLE = "consumable"  # a leaf a user can complete (episode, chapter)
    TRACKABLE = "trackable"  # user state can be attached here
    ORDERED_PARTS = "ordered_parts"  # part coordinates carry meaningful order
    SCAN_ROOT = "scan_root"  # a valid starting point for `scan`


class Status(StrEnum):
    """Provider-neutral status for user state."""

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
    """Temporal precision advertised for a temporal field constraint.

    If the advertised precision is `DATE`, providers should return date values and
    the bridge will reduce incoming datetimes during translation.
    """

    DATE = "date"
    DATETIME = "datetime"


@dataclass(frozen=True, slots=True)
class TemporalConstraint:
    """Accepted temporal granularity for a datetime field."""

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
    """What an incremental change touched.

    Advertises change granularity in `Capabilities.change_kinds`. The payloads are the
    `Change` union.
    """

    NODE = "node"
    RECORD = "record"
    EVENT = "event"


class WriteOp(StrEnum):
    """Write operations a provider may advertise."""

    UPSERT_RECORD = "upsert_record"
    DELETE_RECORD = "delete_record"
    APPEND_EVENT = "append_event"
    DELETE_EVENT = "delete_event"


class WriteError(StrEnum):
    """Machine-readable reason a write failed, so the planner can pick a policy.

    `WriteResult.error` carries the human detail.
    """

    UNSUPPORTED = "unsupported"  # op/field not supported here (don't retry)
    NOT_FOUND = "not_found"  # target ref/record/event doesn't exist
    CONFLICT = "conflict"  # concurrency / state conflict
    INVALID = "invalid"  # malformed or rejected input (don't retry as-is)
    AUTH = "auth"  # auth/permission failure
    RATE_LIMITED = "rate_limited"  # throttled; retry after backoff
    TRANSIENT = "transient"  # transient upstream failure; retryable
    INTERNAL = "internal"  # provider-internal error


class NodeKind(StrEnum):
    """Semantic node kind used for cross-provider classification.

    For display, like-with-like grouping, and choosing the coordinate interpretation.
    Operational sync semantics live in `NodeFlag`. A provider maps its natives onto
    these in `Capabilities.node_kinds`.
    """

    SERIES = "series"
    SEASON = "season"
    EPISODE = "episode"
    FILM = "film"
    BOOK_SERIES = "book_series"
    BOOK = "book"
    CHAPTER = "chapter"
    GAME = "game"


class RecordKind(StrEnum):
    """Semantic record kind: which channel of user state a record belongs to.

    Lets the bridge sync like with like and never mix channels. Single-list providers
    (e.g. AniList, MAL) declare just `PROGRESS`. Multi-list providers (e.g. Trakt) split
    across several. Note `PLANNED` here is a separate list (a watchlist), distinct from
    `Status.PLANNED` (a planning status inside the progress list). A provider maps its
    natives in `Capabilities.record_kinds`.
    """

    PROGRESS = "progress"  # primary consumption state (status/progress/rating)
    COLLECTION = "collection"  # owned / in library
    PLANNED = "planned"  # intent to consume, modeled as its own list
    RATINGS = "ratings"  # ratings kept as a separate list


class EventKind(StrEnum):
    """Semantic event kind. Mapped in `Capabilities.event_kinds`."""

    PLAY = "play"  # a consumption event / scrobble
    CHECKIN = "checkin"  # a user-initiated check-in


# Closed vocabularies a `Descriptor` can map a native string onto.
type Semantic = NodeKind | RecordKind | EventKind | Status


@dataclass(frozen=True, slots=True)
class Descriptor[S: Semantic]:
    """A native vocabulary value mapped onto a closed shared semantic.

    `native` is the provider's exact term (what it puts in `Node.kind` / `Record.kind` /
    `Event.kind`, or a native status label). `semantic` is the closed cross-provider
    meaning the bridge matches on (e.g. native "show" -> `NodeKind.SERIES`).
    `semantic is None` marks the native as provider-private: used only for display.
    """

    native: str
    semantic: S | None = None
    description: str | None = None


@dataclass(frozen=True, slots=True)
class ExternalId:
    """A stable external identity used for cross-provider matching.

    In-memory form of an anibridge-mappings *descriptor*
    (https://github.com/anibridge/anibridge-mappings), whose wire format is
    `authority:value[:scope]`.
    """

    authority: str  # mappings descriptor "provider"
    value: str  # mappings descriptor "id"
    scope: str | None = None  # optional mappings descriptor "scope" for subsetting

    @classmethod
    def parse(cls, descriptor: str) -> ExternalId:
        """Parse an `authority:value[:scope]` descriptor.

        Relies on the dataset invariant that authority/value tokens contain no
        colons, so a 3-field split yields a scope and a 2-field split does not.
        """
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

    axis: str  # e.g. "season", "episode", "chapter", "disc", "track"
    value: int | str


@dataclass(frozen=True, slots=True)
class Ref:
    """Addresses an anchor, or a part within it via `path`.

    `key` is the provider's identifier for the anchor (the mappable unit). An empty
    `path` points at the anchor; a non-empty path points at a coordinate inside it. The
    same (anchor, path) aligns across providers even when one materializes the part as
    its own object and another does not.
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


@dataclass(frozen=True, slots=True)
class Titles:
    """TITLES facet."""

    primary: str
    alternates: dict[str, str] = field(default_factory=dict)  # {lang_code: title}


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
    kind: str  # open string, advertised in `Capabilities.node_kinds`
    title: str | None = None
    url: str | None = None
    labels: tuple[str, ...] = ()  # presentation labels for the web UI
    flags: frozenset[NodeFlag] = field(default_factory=frozenset)
    facets: Mapping[FacetName, Facet] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class State:
    """A lifecycle state: native label plus normalized status."""

    native: str | None = None
    status: Status | None = None


@dataclass(frozen=True, slots=True)
class Progress:
    """A progress channel.

    `unit` is provider-native and open-ended, such as "episode", "page", or
    "minute".
    """

    current: int | float | None
    total: int | float | None = None
    unit: str | None = None


@dataclass(frozen=True, slots=True)
class Rating:
    """A rating with its native scale (e.g. 4.5 on a scale of 5)."""

    value: float
    scale: tuple[float, float, float]  # (min, max, step)


# The value union for record fields. A field is unset by being absent from
# `Record.values`, never by storing `None`.
type Value = State | Progress | Rating | Scalar | date | datetime


@dataclass(frozen=True, slots=True)
class Record:
    """Aggregate user state about a ref.

    `kind` distinguishes coexisting state channels for the same ref, such as Trakt's
    "watched", "collection", and "watchlist" records. Single-list providers should
    use the default kind.

    `revision` is an optional optimistic-concurrency token echoed back on writes. In
    `values`, an absent `RecordField` means "unknown" or "unset". Never store an
    explicit `None`; use `UpsertRecord.clear` to remove fields.
    """

    ref: Ref
    kind: str = ""  # advertised in Capabilities.record_kinds
    key: str | None = None  # provider's record id, if any
    url: str | None = None
    updated_at: datetime | None = None  # last mutation time (UTC); drives LWW
    revision: str | None = None
    ids: tuple[ExternalId, ...] = ()
    values: Mapping[RecordField, Value] = field(default_factory=dict)
    metadata: Mapping[str, MetaValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Event:
    """A timestamped user activity on a ref.

    `at` must be timezone-aware UTC.
    """

    ref: Ref
    kind: str  # advertised in Capabilities.event_kinds
    at: datetime
    key: str | None = None
    metadata: Mapping[str, MetaValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EventSummary:
    """Aggregated event counts for efficient planning.

    `first_at` and `last_at`, when present, must be timezone-aware UTC.
    """

    ref: Ref
    kind: str
    count: int | None = None
    first_at: datetime | None = None
    last_at: datetime | None = None


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

    `total`, when known, is the total number of items matching the query across
    all pages. Providers may leave it unset when calculating a total would require
    extra work or the remote API does not expose one.
    """

    items: tuple[ItemT, ...]
    cursor: str | None = None
    total: int | None = None


@dataclass(frozen=True, slots=True)
class ScanItem:
    """A node paired with its user records during source enumeration."""

    node: Node
    records: tuple[Record, ...] = ()


@dataclass(frozen=True, slots=True)
class NodeQuery:
    """Targeted node lookup.

    Only requested `facets` are hydrated. `native_node_kinds` filters on the
    provider's own open-string kinds, not the closed semantic `NodeKind`.
    """

    refs: tuple[Ref, ...] = ()
    native_node_kinds: tuple[str, ...] = ()
    flags: frozenset[NodeFlag] = field(default_factory=frozenset)
    facets: frozenset[FacetName] = field(default_factory=frozenset)
    cursor: str | None = None
    limit: int | None = None


@dataclass(frozen=True, slots=True)
class RecordQuery:
    """Selective record lookup.

    Only requested `fields` are hydrated. `native_record_kinds` filters on the
    provider's own open-string kinds.
    """

    refs: tuple[Ref, ...] = ()
    keys: tuple[str, ...] = ()
    native_record_kinds: tuple[str, ...] = ()
    fields: frozenset[RecordField] = field(default_factory=frozenset)
    cursor: str | None = None
    limit: int | None = None


@dataclass(frozen=True, slots=True)
class ScanQuery:
    """Source enumeration.

    `ScanQuery` is separate from `NodeQuery`, which is optimized for targeted ref
    lookups. The `native_*_kinds` filters use the provider's own open-string kinds.
    When `with_records` is true, returned scan items may include user records.
    """

    sources: tuple[Ref, ...] = ()  # scan roots; empty means the full catalog
    native_node_kinds: tuple[str, ...] = ()
    flags: frozenset[NodeFlag] = field(default_factory=frozenset)
    facets: frozenset[FacetName] = field(default_factory=frozenset)
    native_record_kinds: frozenset[str] = field(default_factory=frozenset)
    fields: frozenset[RecordField] = field(default_factory=frozenset)
    with_records: bool = True
    require_activity: bool = False  # include only items with user state
    cursor: str | None = None
    limit: int | None = None


@dataclass(frozen=True, slots=True)
class EventQuery:
    """Detailed event lookup.

    `native_event_kinds` filters on the provider's own open-string event kinds.
    """

    refs: tuple[Ref, ...] = ()
    native_event_kinds: tuple[str, ...] = ()
    cursor: str | None = None
    limit: int | None = None


@dataclass(frozen=True, slots=True)
class EventSummaryQuery:
    """Aggregate event lookup.

    `native_event_kinds` filters on the provider's own open-string event kinds.
    """

    refs: tuple[Ref, ...] = ()
    native_event_kinds: tuple[str, ...] = ()
    cursor: str | None = None
    limit: int | None = None


@dataclass(frozen=True, slots=True)
class ChangeQuery:
    """Incremental change-feed poll."""

    cursor: str | None = None
    limit: int | None = None


@dataclass(frozen=True, slots=True)
class UpsertRecord:
    """Create or patch a record.

    `set` applies field values, and `clear` removes fields. `token` is an opaque
    client-side correlation tag echoed on the matching `WriteResult`.
    `expected_revision`, when given, requests optimistic-concurrency checking.
    """

    ref: Ref
    kind: str = ""
    key: str | None = None
    token: str | None = None
    expected_revision: str | None = None
    set: Mapping[RecordField, Value] = field(default_factory=dict)
    clear: frozenset[RecordField] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class DeleteRecord:
    """Delete a record by key, or by (ref, kind)."""

    ref: Ref | None = None
    kind: str = ""
    key: str | None = None
    token: str | None = None


type RecordWrite = UpsertRecord | DeleteRecord


@dataclass(frozen=True, slots=True)
class AppendEvent:
    """Append one activity event.

    `at` must be timezone-aware UTC. Event appends are at-least-once from AniBridge's
    side: `token` is a correlation tag, not a deduplication key. A provider that cannot
    deduplicate naturally should treat a repeated `(ref, kind, at)` as the same event
    to keep retries idempotent.
    """

    ref: Ref
    kind: str
    at: datetime
    token: str | None = None
    metadata: Mapping[str, MetaValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DeleteEvent:
    """Delete an event by key, or by a specific `(ref, kind, at)` signature."""

    key: str | None = None
    ref: Ref | None = None
    kind: str | None = None
    at: datetime | None = None
    token: str | None = None


type EventWrite = AppendEvent | DeleteEvent


@dataclass(frozen=True, slots=True)
class WriteResult:
    """Outcome of one write, returned positionally with its input.

    `token` echoes the request's correlation tag for extra safety. On failure, `code`
    is the machine-readable reason that drives retry, skip, or abort behavior, and
    `error` is optional human-readable detail.
    """

    ok: bool
    op: WriteOp
    token: str | None = None
    key: str | None = None
    ref: Ref | None = None
    revision: str | None = None
    code: WriteError | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class NodeChange:
    """A catalog change.

    `facets` names what changed for targeted rehydration. Empty `facets` means the
    changed facets are unknown and the node should be reread fully.
    """

    ref: Ref | None = None
    key: str | None = None
    at: datetime | None = None  # UTC
    facets: frozenset[FacetName] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class RecordChange:
    """A record change.

    `kind` is the affected record kind. `fields` names what changed for targeted
    rehydration. Empty `fields` means the changed fields are unknown and the record
    should be reread fully.
    """

    ref: Ref | None = None
    key: str | None = None
    kind: str = ""
    at: datetime | None = None  # UTC
    fields: frozenset[RecordField] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class EventChange:
    """An event change. `kind` is the event kind affected."""

    ref: Ref | None = None
    key: str | None = None
    kind: str = ""
    at: datetime | None = None  # UTC


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


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """The contract for one planner-visible record field.

    The value shape is fixed by `RecordField`, so it is not restated here. `constraints`
    declares the provider's native limits for this field, such as date-only datetimes,
    whole-number rating scales, or maximum note length. `values` declares native status
    labels and their semantics for the `STATUS` field.
    """

    field: RecordField
    readable: bool = True
    writable: bool = False
    constraints: tuple[FieldConstraint, ...] = ()
    values: tuple[Descriptor[Status], ...] = ()  # native status labels
    description: str | None = None

    def __post_init__(self) -> None:
        """Reject ambiguous field capability declarations."""
        if self.field != RecordField.STATUS and self.values:
            raise ValueError("FieldSpec.values is only valid for RecordField.STATUS")

        if self.field == RecordField.STATUS and (self.readable or self.writable):
            if not self.values:
                raise ValueError("STATUS fields must declare supported native values")

            seen_native: set[str] = set()
            seen_writable_semantics: set[Status] = set()
            for descriptor in self.values:
                if descriptor.semantic is None:
                    raise ValueError(
                        "STATUS field values must map to a normalized Status"
                    )
                if descriptor.native in seen_native:
                    raise ValueError(
                        f"duplicate STATUS native value: {descriptor.native!r}"
                    )
                seen_native.add(descriptor.native)
                if not self.writable:
                    continue
                if descriptor.semantic in seen_writable_semantics:
                    raise ValueError(
                        f"duplicate writable STATUS semantic: {descriptor.semantic!r}"
                    )
                seen_writable_semantics.add(descriptor.semantic)

        seen: set[type[FieldConstraint]] = set()
        for constraint in self.constraints:
            constraint_type = type(constraint)
            if constraint_type in seen:
                raise ValueError(
                    f"duplicate field constraint type: {constraint_type.__name__}"
                )
            seen.add(constraint_type)


@dataclass(frozen=True, slots=True)
class Capabilities:
    """Provider vocabularies and sub-method granularity.

    Method presence is answered by `isinstance(provider, SupportsX)`. `Capabilities`
    describes what those methods support.

    `node_kinds`, `record_kinds`, and `event_kinds` map native kind strings onto closed
    semantics so the bridge can translate across providers. `coordinate_axes` maps a
    native node kind to its ordered axis vocabulary, such as "show" -> ("season",
    "episode"), so the bridge can know a kind's coordinate space without hydrating
    `STRUCTURE`.

    `external_authorities` holds AniMap descriptor authority tokens this provider can
    emit or resolve. These are mapping-database identifiers, not provider namespaces:
    `Provider.NAMESPACE` identifies the AniBridge plugin/provider implementation, while
    authorities such as "anilist", "tmdb_show", or "tvdb_movie" identify mapping graph
    nodes.
    """

    roles: frozenset[Role] = field(default_factory=frozenset)
    facets: frozenset[FacetName] = field(default_factory=frozenset)
    node_kinds: tuple[Descriptor[NodeKind], ...] = ()
    coordinate_axes: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    record_kinds: tuple[Descriptor[RecordKind], ...] = ()
    record_fields: Mapping[RecordField, FieldSpec] = field(default_factory=dict)
    event_kinds: tuple[Descriptor[EventKind], ...] = ()
    write_ops: frozenset[WriteOp] = field(default_factory=frozenset)
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
    """Source enumeration."""

    @abstractmethod
    async def scan(self, query: ScanQuery) -> Page[ScanItem]:
        """Scan provider content in bulk, optionally including records."""


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
    """Selective record reads."""

    @abstractmethod
    async def fetch_records(self, query: RecordQuery) -> Page[Record]:
        """Fetch records matching the requested field projection."""


class SupportsRecordWrites(ABC):
    """Record mutations. Granularity is advertised in `write_ops`.

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
    """Detailed event reads."""

    @abstractmethod
    async def fetch_events(self, query: EventQuery) -> Page[Event]:
        """Fetch detailed events matching the query."""


class SupportsEventSummaries(ABC):
    """Aggregated event reads for efficient planning."""

    @abstractmethod
    async def fetch_event_summaries(
        self, query: EventSummaryQuery
    ) -> Page[EventSummary]:
        """Fetch aggregate event summaries matching the query."""


class SupportsEventWrites(ABC):
    """Event mutations. Granularity is advertised in `write_ops`."""

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
