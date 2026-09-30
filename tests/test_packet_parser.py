# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Beijing Tinqiao Technology Co., Ltd.
"""PacketParser state-machine tests (hardware-free firmware unit).

The parser is what runs on the Pico — feeding it byte streams in
arbitrary chunks and asserting it produces the right packets is the
only realistic way to test firmware logic without flashing.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add firmware/ to path so we can import packet_parser without flashing
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "firmware"))

from packet_parser import HEADER, PacketParser  # noqa: E402


def _frame(cmd: int, payload: bytes, seq: int = 0) -> bytes:
    """Build a valid wire frame for parser feeding."""
    import struct
    header = bytes([HEADER])
    seq_b = struct.pack("<H", seq)
    cmd_b = bytes([cmd])
    plen = struct.pack("<H", len(payload))
    data = header + seq_b + cmd_b + plen + payload
    csum = sum(data) & 0xFF
    return data + bytes([csum])


class TestBasicExtraction:
    def test_single_complete_frame(self):
        p = PacketParser()
        p.feed(_frame(0x01, b""))
        packets = list(p.iter_packets())
        assert len(packets) == 1
        assert packets[0][0] == HEADER
        assert p.buffer_size == 0

    def test_multiple_frames_in_one_feed(self):
        p = PacketParser()
        p.feed(_frame(0x01, b"") + _frame(0x11, b"\x01\x00"))
        packets = list(p.iter_packets())
        assert len(packets) == 2

    def test_no_complete_frame_returns_empty(self):
        p = PacketParser()
        p.feed(b"\xaa\x00")  # incomplete header preamble
        assert list(p.iter_packets()) == []
        assert p.buffer_size == 2  # bytes retained for next feed


class TestStreaming:
    def test_frame_split_across_two_feeds(self):
        p = PacketParser()
        wire = _frame(0x22, b"hello")
        # Split mid-frame
        p.feed(wire[:4])
        assert list(p.iter_packets()) == []
        p.feed(wire[4:])
        packets = list(p.iter_packets())
        assert len(packets) == 1

    def test_byte_by_byte_streaming(self):
        """Worst-case scenario: parser sees one byte at a time."""
        p = PacketParser()
        wire = _frame(0x10, b"\x01\x02\x03\x04\x00")
        out: list[bytes] = []
        for byte in wire:
            p.feed(bytes([byte]))
            out.extend(p.iter_packets())
        assert len(out) == 1
        assert out[0] == wire


class TestResync:
    def test_garbage_before_header_skipped(self):
        """Parser must drop noise bytes until it finds a 0xAA."""
        p = PacketParser()
        valid = _frame(0x01, b"")
        p.feed(b"\xff\xfe\xdd" + valid)
        packets = list(p.iter_packets())
        assert len(packets) == 1
        assert packets[0] == valid

    def test_invalid_payload_len_drops_and_resyncs(self):
        """A header with bogus plen > MAX_PAYLOAD_LEN must not hang the parser."""
        import struct
        p = PacketParser()
        # Fake header with payload length 0xFFFF (> MAX)
        bogus = bytes([HEADER]) + b"\x00\x00\x01" + struct.pack("<H", 0xFFFF)
        valid = _frame(0x01, b"")
        p.feed(bogus + valid)
        # Parser must recover and yield the valid frame
        packets = list(p.iter_packets())
        assert len(packets) == 1
        assert packets[0] == valid


class TestReset:
    def test_reset_clears_buffer(self):
        p = PacketParser()
        p.feed(b"\xaa\x01\x02")
        assert p.buffer_size > 0
        p.reset()
        assert p.buffer_size == 0
