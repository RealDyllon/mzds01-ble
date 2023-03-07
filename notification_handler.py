from binascii import hexlify

from logger import logger
from main import RESPONSE_UUID


def notification_handler(response, client, event, handle: int, data: bytes) -> None:
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