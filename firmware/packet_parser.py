# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2026 Beijing Tinqiao Technology Co., Ltd.
"""Frame extractor for the ClawTouch HID wire protocol (epoch 1).

Hardware-free — runs on any Python interpreter. Use it to test the
firmware logic on a PC without flashing anything: feed it bytes,
iterate over complete packets it produces, and pass each one to your
own :class:`HidExecutor` (or :func:`process_packet`) for assertions.
"""

import struct

HEADER = 0xAA
MAX_PAYLOAD_LEN = 1024


class PacketParser:
    """Extract complete protocol packets from a continuous byte stream.

    Usage::

        parser = PacketParser()
        parser.feed(incoming_bytes)
        for packet in parser.iter_packets():
            executor.process_packet(packet)
    """

    def __init__(self):
        self._buf = bytearray()

    def feed(self, data: bytes):
        """Append more bytes to the parser's buffer."""
        self._buf.extend(data)

    def iter_packets(self):
        """Yield every complete packet currently in the buffer."""
        while True:
            packet = self._try_extract()
            if packet is None:
                break
            yield packet

    def _try_extract(self) -> bytes | None:
        """Try to extract one complete packet from the buffer head.

        Iterative: a noisy CDC line (or an attacker streaming N bogus
        ``0xAA`` headers each with ``plen > MAX_PAYLOAD_LEN``) used to
        recurse N times here, blowing the Pico's tiny CircuitPython
        stack with ``RecursionError`` after ~1000 bogus headers. The
        same resync now runs as a single ``while`` loop with O(1)
        recursion depth.
        """
        while True:
            # Frame sync: drop bytes until HEADER. ``find`` is one
            # memcpy regardless of how many leading garbage bytes we
            # have, vs the old ``pop(0)`` which was O(K²) on a
            # K-byte garbage prefix (memmove per byte).
            sync_idx = self._buf.find(HEADER)
            if sync_idx < 0:
                # No header in buffer at all — drop everything and wait
                # for more bytes.
                self._buf.clear()
                return None
            if sync_idx > 0:
                del self._buf[:sync_idx]

            # Need at least header(1) + seq(2) + cmd(1) + plen(2) = 6 bytes
            if len(self._buf) < 6:
                return None

            payload_len = struct.unpack_from("<H", self._buf, 4)[0]

            if payload_len > MAX_PAYLOAD_LEN:
                # Invalid length: drop this HEADER and resync (loop).
                del self._buf[:1]
                continue

            # Full packet = 6 byte preamble + payload + 1 byte checksum
            total_len = 7 + payload_len
            if len(self._buf) < total_len:
                return None

            packet = bytes(self._buf[:total_len])
            del self._buf[:total_len]
            return packet

    def reset(self):
        """Clear the buffer."""
        self._buf.clear()

    @property
    def buffer_size(self) -> int:
        return len(self._buf)
