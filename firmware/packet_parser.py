"""Frame extractor for the ClawTouch HID v1.0 wire protocol.

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
        """Try to extract one complete packet from the buffer head."""
        # Frame sync: drop bytes until HEADER
        while self._buf and self._buf[0] != HEADER:
            self._buf.pop(0)

        # Need at least header(1) + seq(2) + cmd(1) + plen(2) = 6 bytes
        if len(self._buf) < 6:
            return None

        payload_len = struct.unpack_from("<H", self._buf, 4)[0]

        if payload_len > MAX_PAYLOAD_LEN:
            # Invalid length: drop this HEADER and resync
            self._buf.pop(0)
            return self._try_extract()

        # Full packet = 6 byte preamble + payload + 1 byte checksum
        total_len = 7 + payload_len
        if len(self._buf) < total_len:
            return None

        packet = bytes(self._buf[:total_len])
        self._buf = self._buf[total_len:]
        return packet

    def reset(self):
        """Clear the buffer."""
        self._buf.clear()

    @property
    def buffer_size(self) -> int:
        return len(self._buf)
