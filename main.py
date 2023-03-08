import sys
import asyncio
from asyncio import Event
from time import sleep
from datetime import datetime
from binascii import hexlify
from typing import Dict, Any, List, Callable, Optional
from bleak import BleakScanner, BleakClient
from bleak.backends.device import BLEDevice as BleakDevice

from classes import Response
from logger import logger
from codes import codes
from codes import BLUETOOTH_ADDRESS, RESPONSE_UUID

def exception_handler(loop: asyncio.AbstractEventLoop, context: Dict[str, Any]) -> None:
    msg = context.get("exception", context["message"])
    logger.error(f"Caught exception {str(loop)}: {msg}")
    logger.critical("This is unexpected and unrecoverable.")


async def connect_ble(
    notification_handler: Callable[[int, bytes], None],
) -> BleakClient:

    asyncio.get_event_loop().set_exception_handler(exception_handler)

    RETRIES = 10
    for retry in range(RETRIES):
        try:
            # Map of discovered devices indexed by name
            devices: Dict[str, BleakDevice] = {}

            # Scan for devices
            logger.info("Scanning for bluetooth devices...")
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
                # Now look for our matching device
                address = BLUETOOTH_ADDRESS
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

            # Enable notifications on all notifiable characteristics
            logger.info("Enabling notifications, reading and writing...")
            for service in client.services:
                for char in service.characteristics:
                    # logger.info(" ".join(char.properties))
                    if "notify" in char.properties and char.uuid[0] != "0":
                        logger.info(f"Enabling notification on char {char.uuid}")
                        await client.start_notify(char, notification_handler)  # type: ignore
                        # break
                    sleep(0.1)
                    if "write" in char.properties:
                        logger.info(f"Writing to char {char.uuid}")
                        await client.write_gatt_char(
                            # "B02EAEAA-F6BC-4A7E-BC94-F7B7FC8DEDOB",
                            char,
                            bytearray([0xFE, 0x01, 0x00, 0x02, 0x50, 0x11]), response=True)
                        sleep(0.1)
                        await client.write_gatt_char(
                            # "B02EAEAA-F6BC-4A7E-BC94-F7B7FC8DEDOB",
                            char,
                            bytearray([0xFE, 0x01, 0x00, 0x02, 0x30, 0x04]), response=True)

                        today = datetime.now()
                        datetime_now_str = today.strftime("%Y%m%d%H%M%S")
                        # logger.info(f"today's datetime: {datetime_now_str}")
                        datetime_now_bytes = datetime_now_str.encode()
                        payload = bytearray([0xFE, 0x01, 0x00, 0x10, 0x50, 0x01])
                        payload.extend(datetime_now_bytes)
                        await client.write_gatt_char(
                            # "B02EAEAA-F6BC-4A7E-BC94-F7B7FC8DEDOB",
                            char, payload, response=True)

                    if "read" in char.properties:
                        logger.info(f"Reading from {char.uuid}")
                        await client.read_gatt_char(char)
            logger.info("Done enabling notifications")

            for service in client.services:
                for char in service.characteristics:
                    if "read" in char.properties:
                        logger.info(f"Reading from {char.uuid}")
                        await client.read_gatt_char(char)

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


async def write_to_client(client: BleakClient, event: Event, data: bytes | bytearray | memoryview, comment: Optional[str]) -> None:
    for service in client.services:
        for char in service.characteristics:
            if "write" in char.properties:
                logger.info(f"Writing to char {char.uuid} ({comment})")
                # event.clear()
                await client.write_gatt_char(char, data, response=True)
                # await event.wait()

async def main() -> None:

    event = asyncio.Event()


    client: BleakClient
    response = Response()

    def notification_handler(handle: int, data: bytes) -> None:
        logger.info(f'Received response at {handle=}: {hexlify(data, ":")!r}')

        response.accumulate(data)

        if response.is_received:
            response.parse()

            # If this is the correct handle and the status is success, the command was a success
            if client.services.characteristics[handle].uuid == RESPONSE_UUID and response.status == 0:
                logger.info("Successfully received the response")
            # Anything else is unexpected. This shouldn't happen
            else:
                logger.error("Unexpected response")

            # Notify writer that procedure is complete
            event.set()


    # find and connect to client
    client = await connect_ble(notification_handler)


    event.clear()
    # await write_to_client(client, event, codes["colors"]["OFF"], "Turning Off")
    await write_to_client(client, event, codes["colors"]["ON"], "Turning On Light")
    sleep(2)
    await write_to_client(client, event, codes["colors"]["WWHITE"], "Warm white")
    sleep(2)
    await write_to_client(client, event, codes["colors"]["DBLUE"], "Dark Blue")
    sleep(2)
    new_brightness = codes["brightness"]["custom"].copy()
    new_brightness.extend([0x10])
    await write_to_client(client, event, new_brightness, "Set brightness to 0x10")
    sleep(2)
    new_brightness = codes["brightness"]["custom"].copy()
    new_brightness.extend([0x64])
    await write_to_client(client, event, new_brightness, "Set brightness to 0x64")
    sleep(2)
    await write_to_client(client, event, codes["colors"]["GREEN"], "Green")
    sleep(2)
    await write_to_client(client, event, codes["colors"]["LBLUE"], "Light Blue")
    sleep(2)
    yellow = codes["colors"]["BASE"].copy()
    yellow.extend([0xFF, 0xFF, 0x00, 0x00]) # rgb then trailing 0x00
    await write_to_client(client, event, yellow, "Yellow")
    sleep(2)
    await write_to_client(client, event, codes["colors"]["OFF"], "Turning Off")

    logger.info("Disconnecting...")

    await client.disconnect()
    logger.info("Disconnected")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(e)
        sys.exit(-1)
    else:
        sys.exit(0)