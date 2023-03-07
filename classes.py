import enum
import json
from typing import Dict

from logger import logger


class Response:
    def __init__(self) -> None:
        self.bytes_remaining = 0
        self.bytes = bytearray()
        self.data: Dict[int, bytes] = {}
        self.id: int
        self.status: int

    def __str__(self) -> str:
        return json.dumps(self.data, indent=4, default=lambda x: x.hex(":"))

    @property
    def is_received(self) -> bool:
        return len(self.bytes) > 0 and self.bytes_remaining == 0

    def accumulate(self, data: bytes) -> None:
        CONT_MASK = 0b10000000
        HDR_MASK = 0b01100000
        GEN_LEN_MASK = 0b00011111
        EXT_13_BYTE0_MASK = 0b00011111

        class Header(enum.Enum):
            GENERAL = 0b00
            EXT_13 = 0b01
            EXT_16 = 0b10
            RESERVED = 0b11

        buf = bytearray(data)
        if buf[0] & CONT_MASK:
            buf.pop(0)
        else:
            # This is a new packet so start with an empty byte array
            self.bytes = bytearray()
            hdr = Header((buf[0] & HDR_MASK) >> 5)
            if hdr is Header.GENERAL:
                self.bytes_remaining = buf[0] & GEN_LEN_MASK
                buf = buf[1:]
            elif hdr is Header.EXT_13:
                self.bytes_remaining = ((buf[0] & EXT_13_BYTE0_MASK) << 8) + buf[1]
                buf = buf[2:]
            elif hdr is Header.EXT_16:
                self.bytes_remaining = (buf[1] << 8) + buf[2]
                buf = buf[3:]

        # Append payload to buffer and update remaining / complete
        self.bytes.extend(buf)
        self.bytes_remaining -= len(buf)
        logger.info(f"{self.bytes_remaining=}")

    def parse(self) -> None:
        self.id = self.bytes[0]
        self.status = self.bytes[1]
        buf = self.bytes[2:]
        while len(buf) > 0:
            # Get ID and Length
            param_id = buf[0]
            param_len = buf[1]
            buf = buf[2:]
            # Get the value
            value = buf[:param_len]

            # Store in dict for later access
            self.data[param_id] = value

            # Advance the buffer
            buf = buf[param_len:]
