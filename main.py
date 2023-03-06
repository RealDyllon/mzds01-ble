import re
import sys
import json
import enum
import asyncio
import argparse
from time import sleep

from binascii import hexlify
from typing import Dict, Any, List, Callable, Optional

from bleak import BleakScanner, BleakClient
from bleak.backends.device import BLEDevice as BleakDevice

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


def exception_handler(loop: asyncio.AbstractEventLoop, context: Dict[str, Any]) -> None:
    msg = context.get("exception", context["message"])
    logger.error(f"Caught exception {str(loop)}: {msg}")
    logger.critical("This is unexpected and unrecoverable.")


async def connect_ble(
    notification_handler: Callable[[int, bytes], None],
    identifier: Optional[str] = None,
) -> BleakClient:
    """Connect to a GoPro, then pair, and enable notifications

    If identifier is None, the first discovered GoPro will be connected to.

    Retry 10 times

    Args:
        notification_handler (Callable[[int, bytes], None]): callback when notification is received
        identifier (str, optional): Last 4 digits of GoPro serial number. Defaults to None.

    Raises:
        Exception: couldn't establish connection after retrying 10 times

    Returns:
        BleakClient: connected client
    """

    asyncio.get_event_loop().set_exception_handler(exception_handler)

    RETRIES = 10
    for retry in range(RETRIES):
        try:
            # Map of discovered devices indexed by name
            devices: Dict[str, BleakDevice] = {}

            # Scan for devices
            logger.info("Scanning for bluetooth devices...")
            # Scan callback to also catch nonconnectable scan responses
            # pylint: disable=cell-var-from-loop
            def _scan_callback(device: BleakDevice, _: Any) -> None:
                # Add to the dict if not unknown
                if device.name and device.name != "Unknown":
                    devices[device.name] = device

            # Scan until we find devices
            matched_devices: List[BleakDevice] = []
            while len(matched_devices) == 0:
                # Now get list of connectable advertisements
                for device in await BleakScanner.discover(timeout=5, detection_callback=_scan_callback):
                    device: BleakDevice = device
                    if True:  # device.name != "Unknown" and device.name is not None:
                        devices[device.address] = device
                # Log every device we discovered
                for d in devices:
                    logger.info(f"\tDiscovered: {d}")
                # Now look for our matching device(s)
                # token = re.compile(r"GoPro [A-Z0-9]{4}" if identifier is None else f"GoPro {identifier}")`
                address = "EC1FF10F-D43D-3B21-9D77-D6CBC851E5EC"
                matched_devices = [device for name, device in devices.items() if name == address]
                print(f"Found {len(matched_devices)} matching devices.")

            # Connect to first matching Bluetooth device
            device = matched_devices[0]

            logger.info(f"Establishing BLE connection to {device}...")
            client = BleakClient(device)
            await client.connect(timeout=15)
            logger.info("BLE Connected!")

            # Try to pair (on some OS's this will expectedly fail)
            logger.info("Attempting to pair...")
            try:
                await client.pair()
            except NotImplementedError:
                # This is expected on Mac
                pass
            logger.info("Pairing complete!")

            # logger.info("sleeping for 10s")
            # sleep(10)
            # logger.info("waking up")

            # NOTE: this light seems to require a time-sensitive handshake

            # Enable notifications on all notifiable characteristics
            logger.info("Enabling notifications...")
            for service in client.services:
                for char in service.characteristics:
                    if "notify" in char.properties and char.uuid[0] != "0":
                        logger.info(f"Enabling notification on char {char.uuid}")
                        await client.start_notify(char, notification_handler)  # type: ignore
                        # break

                    if "write" in char.properties:
                        logger.info(f"Writing to char {char.uuid}")
                        await client.write_gatt_char(
                            # "B02EAEAA-F6BC-4A7E-BC94-F7B7FC8DEDOB",
                            char,
                            bytearray([0xFE, 0x01, 0x00, 0x02, 0x50, 0x11]), response=True)
                        await client.write_gatt_char(
                            # "B02EAEAA-F6BC-4A7E-BC94-F7B7FC8DEDOB",
                            char,
                            bytearray([0xFE, 0x01, 0x00, 0x10, 0x50, 0x01, 0x32, 0x30, 0x32, 0x33, 0x30, 0x33]), response=True)

                        # await client.read_gatt_char(char)
            logger.info("Done enabling notifications")

            # enable write like iphone
            # logger.info("Going to send a 2nd packet")
            # for service in client.services:
            #     for char in service.characteristics:
            #
            # logger.info("Finished sending a 2nd packet")

            return client
        except Exception as e:
            logger.error(f"Connection establishment failed: {e}")
            logger.warning(f"Retrying #{retry}")

    raise Exception(f"Couldn't establish BLE connection after {RETRIES} retries")


async def main(identifier: Optional[str]) -> None:

    event = asyncio.Event()

    # UUIDs to write to and receive responses from
    QUERY_REQ_UUID = "10e2fde2-d7fe-4845-b3f3-a32010ebb095"
    # QUERY_RSP_UUID = "smth"

    #     "fa879af4-d601-420c-b2b4-07ffb528dde3",
    #     "0000ae00-0000-1000-8000-00805f9b34fb"
    response_uuid = "fa879af4-d601-420c-b2b4-07ffb528dde3" # QUERY_RSP_UUID

    client: BleakClient
    response = Response()

    def notification_handler(handle: int, data: bytes) -> None:
        logger.info(f'Received response at {handle=}: {hexlify(data, ":")!r}')

        response.accumulate(data)

        if response.is_received:
            response.parse()

            # If this is the correct handle and the status is success, the command was a success
            if client.services.characteristics[handle].uuid == response_uuid and response.status == 0:
                logger.info("Successfully received the response")
            # Anything else is unexpected. This shouldn't happen
            else:
                logger.error("Unexpected response")

            # Notify writer that procedure is complete
            event.set()

    # find and connect to client
    client = await connect_ble(notification_handler, identifier)

    # logger.info("Client services:")
    # for service in client.services:
    #     logger.info(f"{service.uuid} - ({len(service.characteristics)})")

    # get characteristics
    logger.info("Getting the device's settings...")
    event.clear()
    # await client.write_gatt_char(QUERY_REQ_UUID, bytearray([0x01, 0x12]), response=True)
    # await client.read_gatt_char("Reading is not permitted")
    # await event.wait()  # Wait to receive the notification response
    logger.info(f"Received settings\n: {response}")

    await client.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Connect to a GoPro camera, pair, then enable notifications.")
    parser.add_argument(
        "-i",
        "--identifier",
        type=str,
        help="Last 4 digits of GoPro serial number, which is the last 4 digits of the default camera SSID. \
            If not used, first discovered GoPro will be connected to",
        default=None,
    )
    args = parser.parse_args()

    try:
        asyncio.run(main(args.identifier))
    except Exception as e:
        logger.error(e)
        sys.exit(-1)
    else:
        sys.exit(0)