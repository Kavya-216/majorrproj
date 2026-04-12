from __future__ import annotations

import os

import pytest

from ecosentry.arch6_payload import AlertPayloadCodec, DeviceMetadata, PayloadSecurityError
from ecosentry.config import load_canonical_config
from ecosentry.contracts import Arch5Result


def test_arch6_encode_decode_roundtrip() -> None:
    cfg = load_canonical_config("config/canonical_config.json")
    codec = AlertPayloadCodec(cfg, os.urandom(32), os.urandom(32))

    arch5 = Arch5Result(class_id=1, confidence=0.89, timestamp_ms=1_765_000_123_000)
    meta = DeviceMetadata(device_id="SENTRY_07", location_hash="HASH_001", firmware_version="1.2.0")

    encoded = codec.encode(arch5, meta)
    decoded = codec.decode(encoded.encrypted_payload_bytes)

    assert decoded["class_id"] == 1
    assert abs(decoded["confidence"] - 0.89) <= 0.01
    assert encoded.size_report.enveloped_bytes <= cfg.payload_max_bytes


def test_arch6_tamper_detected() -> None:
    cfg = load_canonical_config("config/canonical_config.json")
    codec = AlertPayloadCodec(cfg, os.urandom(32), os.urandom(32))

    arch5 = Arch5Result(class_id=2, confidence=0.93, timestamp_ms=1_765_000_555_000)
    meta = DeviceMetadata(device_id="SENTRY_08", location_hash="HASH_002", firmware_version="1.2.1")

    encoded = codec.encode(arch5, meta)
    tampered = bytearray(encoded.encrypted_payload_bytes)
    tampered[20] ^= 0x01

    with pytest.raises(PayloadSecurityError):
        codec.decode(bytes(tampered))
