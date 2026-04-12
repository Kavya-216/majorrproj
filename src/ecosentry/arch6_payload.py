from __future__ import annotations

import hmac
import json
import os
import struct
import zlib
from dataclasses import asdict, dataclass
from binascii import crc_hqx
from hashlib import sha256
from typing import Any

from cryptography.hazmat.primitives import hashes, hmac as crypto_hmac, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .config import CanonicalConfig
from .contracts import Arch5Result, CLASS_MAP

MAGIC = b"\xEC\xEA"
PROTOCOL_VERSION = 1
TAG_LEN = 16


@dataclass(frozen=True)
class DeviceMetadata:
    device_id: str
    location_hash: str
    firmware_version: str


@dataclass(frozen=True)
class PayloadField:
    key: str
    datatype: str
    description: str


@dataclass(frozen=True)
class SizeReport:
    raw_json_bytes: int
    compressed_bytes: int
    encrypted_bytes: int
    enveloped_bytes: int


@dataclass(frozen=True)
class EnvelopeMetadata:
    magic_hex: str
    version: int
    sequence_number: int
    iv_hex: str
    hmac_sha256_hex: str
    cipher_length: int


@dataclass(frozen=True)
class Arch6Result:
    encrypted_payload_bytes: bytes
    envelope_metadata: EnvelopeMetadata
    size_report: SizeReport


class PayloadSecurityError(Exception):
    pass


class AlertPayloadCodec:
    """ARCH_6 codec: serialize -> compress -> encrypt -> envelope and reverse."""

    def __init__(self, config: CanonicalConfig, encryption_key: bytes, hmac_key: bytes):
        if len(encryption_key) != 32:
            raise ValueError("encryption_key must be 32 bytes for AES-256")
        if len(hmac_key) < 32:
            raise ValueError("hmac_key must be at least 32 bytes")

        self.config = config
        self.encryption_key = encryption_key
        self.hmac_key = hmac_key
        self._sequence = 0

    @staticmethod
    def compact_field_dictionary() -> list[PayloadField]:
        return [
            PayloadField("t", "uint64", "timestamp in unix epoch milliseconds"),
            PayloadField("d", "uint16", "device identifier crc16 (registry lookup at receiver)"),
            PayloadField("c", "uint8", "class id: 0 gunshot, 1 chainsaw, 2 vehicle"),
            PayloadField("p", "uint8", "confidence percentage 0-100"),
            PayloadField("l", "uint16", "location hash crc16 (grid lookup at receiver)"),
            PayloadField("v", "uint8", "firmware major version"),
        ]

    def _next_sequence(self) -> int:
        current = self._sequence
        self._sequence = (self._sequence + 1) % (2**32)
        return current

    @staticmethod
    def _crc16(value: str) -> int:
        return int(crc_hqx(value.encode("utf-8"), 0) & 0xFFFF)

    @staticmethod
    def _fw_major(version: str) -> int:
        try:
            return int(version.split(".")[0])
        except (ValueError, IndexError):
            return 0

    def _serialize_json(self, arch5: Arch5Result, meta: DeviceMetadata, sequence_number: int) -> bytes:
        arch5.validate()
        payload = {
            "t": arch5.timestamp_ms,
            "d": self._crc16(meta.device_id),
            "c": arch5.class_id,
            "p": int(round(arch5.confidence * 100)),
            "l": self._crc16(meta.location_hash),
            "v": self._fw_major(meta.firmware_version),
        }
        return json.dumps(payload, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def _compress(raw_json: bytes) -> bytes:
        return zlib.compress(raw_json, level=9)

    def _encrypt_cbc(self, compressed: bytes) -> tuple[bytes, bytes]:
        iv = os.urandom(16)
        padder = padding.PKCS7(128).padder()
        padded = padder.update(compressed) + padder.finalize()
        cipher = Cipher(algorithms.AES(self.encryption_key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded) + encryptor.finalize()
        return iv, ciphertext

    def _build_envelope(self, sequence_number: int, iv: bytes, ciphertext: bytes) -> tuple[bytes, bytes]:
        cipher_len = len(ciphertext)
        header = MAGIC + struct.pack(">BBIH", PROTOCOL_VERSION, 0, sequence_number, cipher_len)
        mac_data = header + iv + ciphertext
        h = crypto_hmac.HMAC(self.hmac_key, hashes.SHA256())
        h.update(mac_data)
        mac = h.finalize()[:TAG_LEN]
        envelope = mac_data + mac
        return envelope, mac

    def encode(self, arch5: Arch5Result, meta: DeviceMetadata) -> Arch6Result:
        mode = self.config.encryption_mode.upper()
        if mode != "AES-256-CBC":
            raise ValueError(f"Unsupported frozen encryption mode: {mode}")

        seq = self._next_sequence()
        raw_json = self._serialize_json(arch5, meta, seq)
        compressed = self._compress(raw_json)
        iv, ciphertext = self._encrypt_cbc(compressed)
        enveloped, mac = self._build_envelope(seq, iv, ciphertext)

        size_report = SizeReport(
            raw_json_bytes=len(raw_json),
            compressed_bytes=len(compressed),
            encrypted_bytes=len(iv) + len(ciphertext),
            enveloped_bytes=len(enveloped),
        )

        if size_report.enveloped_bytes > self.config.payload_max_bytes:
            raise ValueError(
                f"payload {size_report.enveloped_bytes} exceeds hard limit {self.config.payload_max_bytes}"
            )

        metadata = EnvelopeMetadata(
            magic_hex=MAGIC.hex(),
            version=PROTOCOL_VERSION,
            sequence_number=seq,
            iv_hex=iv.hex(),
            hmac_sha256_hex=mac.hex(),
            cipher_length=len(ciphertext),
        )

        return Arch6Result(
            encrypted_payload_bytes=enveloped,
            envelope_metadata=metadata,
            size_report=size_report,
        )

    def decode(self, envelope: bytes) -> dict[str, Any]:
        if len(envelope) < 2 + 1 + 1 + 4 + 2 + 16 + TAG_LEN:
            raise PayloadSecurityError("Envelope too short")

        magic = envelope[:2]
        if magic != MAGIC:
            raise PayloadSecurityError("Invalid magic bytes")

        version, flags = struct.unpack(">BB", envelope[2:4])
        if version != PROTOCOL_VERSION:
            raise PayloadSecurityError(f"Unsupported protocol version {version}")
        _ = flags

        sequence_number = struct.unpack(">I", envelope[4:8])[0]
        cipher_len = struct.unpack(">H", envelope[8:10])[0]

        iv = envelope[10:26]
        cipher_start = 26
        cipher_end = cipher_start + cipher_len
        if cipher_end + TAG_LEN > len(envelope):
            raise PayloadSecurityError("Corrupted envelope lengths")

        ciphertext = envelope[cipher_start:cipher_end]
        recv_mac = envelope[cipher_end : cipher_end + TAG_LEN]

        mac_data = envelope[:cipher_end]
        expected_mac = hmac.new(self.hmac_key, mac_data, sha256).digest()[:TAG_LEN]
        if not hmac.compare_digest(recv_mac, expected_mac):
            raise PayloadSecurityError("Integrity verification failed")

        cipher = Cipher(algorithms.AES(self.encryption_key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()

        unpadder = padding.PKCS7(128).unpadder()
        compressed = unpadder.update(padded) + unpadder.finalize()

        raw = zlib.decompress(compressed)
        payload = json.loads(raw.decode("utf-8"))

        return {
            "timestamp_ms": int(payload["t"]),
            "device_id_crc16": int(payload["d"]),
            "class_id": int(payload["c"]),
            "confidence": float(payload["p"]) / 100.0,
            "location_crc16": int(payload["l"]),
            "firmware_major": int(payload["v"]),
            "sequence_number": sequence_number,
            "class_label": CLASS_MAP[int(payload["c"])],
        }

    @staticmethod
    def metadata_to_dict(meta: EnvelopeMetadata) -> dict[str, Any]:
        return asdict(meta)
