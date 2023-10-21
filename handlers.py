from typing import Union

from discord import Message


async def get_yes_no(message: Message) -> Union[bool, None]:
    msg = message.content.lower()
    if msg in ['yes', 'y']:
        return True
    elif msg in ['no', 'n']:
        return False
    else:
        await message.channel.send("Invalid response. Please respond with 'yes' or 'no'")
        return
