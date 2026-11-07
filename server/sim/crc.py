"""CRC-16/CCITT-FALSE, the Packet v1 checksum (docs/specs/packet-format-v1.md)."""

POLYNOMIAL = 0x1021
INITIAL = 0xFFFF


def crc16_ccitt_false(data: bytes) -> int:
    """Polynomial 0x1021, initial 0xFFFF, no reflection, final XOR 0x0000."""
    crc = INITIAL
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ POLYNOMIAL) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc
