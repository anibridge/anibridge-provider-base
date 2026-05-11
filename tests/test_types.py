"""Tests for anibridge.provider.types."""

import logging

from anibridge.provider import (
    Key,
    Logger,
    MappingRef,
    ResolvedMapping,
    SerializedState,
    WebhookPayload,
    WebhookResult,
)


def test_mapping_ref_and_resolved_mapping_are_explicit_value_objects() -> None:
    """Mapping types should expose clear structured values."""

    mapping = MappingRef(provider="anilist", id="123")
    resolved = ResolvedMapping(mapping=mapping, key="abc")
    serialized_state: SerializedState = {"status": "completed"}

    assert Key.__value__ is str
    assert dict(serialized_state) == {"status": "completed"}
    assert mapping == MappingRef(provider="anilist", id="123")
    assert mapping.scope is None
    assert resolved.mapping is mapping
    assert resolved.key == "abc"


def test_webhook_payload_and_result_defaults_are_stable() -> None:
    """Webhook types should provide predictable empty defaults."""

    payload = WebhookPayload()
    result = WebhookResult()
    head_payload = WebhookPayload(method="HEAD")

    assert payload.body == b""
    assert payload.headers == {}
    assert payload.params == {}
    assert payload.method == "POST"
    assert payload.path == ""
    assert head_payload.method == "HEAD"
    assert result == WebhookResult(matched=False, keys=())


def test_provider_logger_extends_logging_logger_with_success_stub() -> None:
    """Provider logger should extend the standard logger surface."""

    assert issubclass(Logger, logging.Logger)
    assert "success" in Logger.__dict__
