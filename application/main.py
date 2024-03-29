
import sys
sys.path.append('..')

from utils import *
import tkinter as tk
import asyncio
from bleak import discover, BleakClient
from logger import logger
from controller import Controller
from gui import Application


async def main():
    devices = await discover()
    print("searching for devices...")
    for d in devices:
        # logger.info(f"\tDiscovered: {d}")
        print(d.address)
        if d.address == LED_BLUETOOTH_ADDRESS:
            print("device found, connecting...")
            ember = d
            break
    else:
        print('LED is not found. Exiting...')
        return

    async with BleakClient(ember.address) as client:
        x = client.is_connected
        print("Connected: {0}".format(x))
        try:
            # await client.pair()
            cont = Controller(client, True)
            root = tk.Tk()
            root.protocol("WM_DELETE_WINDOW", lambda: asyncio.gather(cont.quit()))
            root.title('LED Controller')
            gui = Application(cont, master=root)
            await cont.start_with_gui(gui)
        except Exception as e:
            import traceback
            traceback.print_exc()
            await client.disconnect()


if __name__ == '__main__':
    asyncio.run(main())