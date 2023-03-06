#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
from typing import Optional

from bleak import BleakClient, BleakScanner, BLEDevice
from time import sleep

# address = "14:7D:DA:16:CF:66"
address = "EC1FF10F-D43D-3B21-9D77-D6CBC851E5EC"
service_uuids = [
    "fa879af4-d601-420c-b2b4-07ffb528dde3",
    "0000ae00-0000-1000-8000-00805f9b34fb"
]

async def main(address: str):
    """ Main program """
    print("running")

    stop_event = asyncio.Event()

    # devices = await BleakScanner.discover()
    #
    # for d in devices:
    #     print(d)



    # pass

    # def callback(device, advertising_data):
    #     # TODO: do something with incoming data
    #     pass

    # async with BleakScanner(callback) as scanner:
    #     # ...
    #     # Important! Wait for an event to trigger stop, otherwise scanner
    #     # will stop immediately.
    #     # await stop_event.wait()
    #     # await scanner.start()
    #     # sleep(5)
    #     # await scanner.stop()
    #
    #     # print(scanner.discovered_devices)
    #
    #     bledevice: Optional[BLEDevice] = await scanner.find("MZDS01")
    #
    #     print(bledevice.address)

    # scanner stops when block exits



    async with BleakClient(address) as client:
        print("connected to: " + client.address + " ")
        print("services")
        for s in client.services:
            print(f"- {s.uuid}   {s.characteristics}   {s.handle} ")
            try:
                for char in s.characteristics:
                    if "notify" in char.properties:
                        pass
                        # await client.start_notify(char, notification_handler)
                char = await client.read_gatt_char(s.uuid)
                print("\nCharacteristic: {0}\n".format("".join(map(chr, char))))
            except:
                pass
    return 0

if __name__ == "__main__":
    asyncio.run(main(address))
