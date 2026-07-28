"""
Binary burst assembler for the BLE transport.

Wire format (matches firmware exactly — see current_uploaded.ino):

  SAMPLE packet (11 bytes):  '<BHff'
      [0]   type = 0x00
      [1:3] sample_index   (uint16, LE)
      [3:7] time_us        (float32, LE)
      [7:11] voltage       (float32, LE)

  END packet (3 bytes): '<BH'
      [0]   type = 0x01
      [1:3] total_count    (uint16, LE)

Serial keeps the original CSV/TraceParser path untouched — this class is
BLE-only, since BLE is the only transport that drops packets.
"""

import struct
from typing import List, Optional, Set

PACKET_TYPE_SAMPLE = 0x00
PACKET_TYPE_END = 0x01

SAMPLE_STRUCT = struct.Struct('<BHff')   # 11 bytes
END_STRUCT = struct.Struct('<BH')        # 3 bytes

TARGET_SAMPLES = 700
MAX_RESEND_ROUNDS = 5          # hard cap so a dead link can't hang forever
INDICES_PER_RESEND_PACKET = 8  # (20 - 2) // 2, fits one BLE write payload


class BLEBurstAssembler:
    """Accumulates SAMPLE packets for one burst, detects gaps on END.

    One instance is reused across bursts — call start_new_burst() when a
    fresh burst begins (i.e. right after finalizing/discarding the previous
    one), so stale data from a prior burst never leaks into the next.
    """

    def __init__(self, total_samples: int = TARGET_SAMPLES):
        self.total_samples = total_samples
        self._voltages: List[Optional[float]] = [None] * total_samples
        self._received: Set[int] = set()
        self._resend_round = 0
        self._ended = False

    def start_new_burst(self):
        self._voltages = [None] * self.total_samples
        self._received.clear()
        self._resend_round = 0
        self._ended = False

    def feed(self, raw: bytes):
        """Process one incoming BLE notification payload.

        Returns one of:
          ('sample', index)   — a sample was stored
          ('end', total)      — END marker seen; caller should check completeness
          ('malformed', None) — packet didn't match either known format (ignored)
        """
        if not raw:
            return ('malformed', None)

        packet_type = raw[0]

        if packet_type == PACKET_TYPE_SAMPLE and len(raw) >= SAMPLE_STRUCT.size:
            _, index, time_us, voltage = SAMPLE_STRUCT.unpack(raw[:SAMPLE_STRUCT.size])
            if 0 <= index < self.total_samples:
                self._voltages[index] = voltage
                self._received.add(index)
                return ('sample', index)
            return ('malformed', None)

        if packet_type == PACKET_TYPE_END and len(raw) >= END_STRUCT.size:
            _, total = END_STRUCT.unpack(raw[:END_STRUCT.size])
            self._ended = True
            return ('end', total)

        return ('malformed', None)

    @property
    def is_complete(self) -> bool:
        return len(self._received) == self.total_samples

    @property
    def missing_indices(self) -> List[int]:
        return sorted(set(range(self.total_samples)) - self._received)

    @property
    def ended(self) -> bool:
        return self._ended

    def can_retry(self) -> bool:
        return self._resend_round < MAX_RESEND_ROUNDS

    def note_resend_round(self):
        self._resend_round += 1

    def get_voltages_or_none(self) -> Optional[List[float]]:
        """Returns the full array only if every slot was actually filled.

        Never returns partially-filled data silently — the caller decides
        explicitly what to do with an incomplete burst (e.g. drop it and log
        a data-loss warning) rather than accidentally feeding None/garbage
        into the regression math.
        """
        if not self.is_complete:
            return None
        return list(self._voltages)  # type: ignore[list-item]


def build_start_command() -> bytes:
    return bytes([0x01])


def build_stop_command() -> bytes:
    return bytes([0x02])


def build_burst_ack_command() -> bytes:
    return bytes([0x04])


def build_resend_commands(missing_indices: List[int]) -> List[bytes]:
    """Chunks missing indices into one or more RESEND command packets.

    Each packet: [0x03][count][idx0_lo][idx0_hi]...  — count <= 8 so the
    whole thing fits in one 20-byte BLE write, no fragmentation needed.
    """
    commands = []
    for start in range(0, len(missing_indices), INDICES_PER_RESEND_PACKET):
        chunk = missing_indices[start:start + INDICES_PER_RESEND_PACKET]
        payload = bytes([0x03, len(chunk)])
        for idx in chunk:
            payload += struct.pack('<H', idx)
        commands.append(payload)
    return commands