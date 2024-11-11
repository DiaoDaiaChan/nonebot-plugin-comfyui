
import json
import aiohttp

from argparse import Namespace

import nonebot
from nonebot import logger, Bot
from nonebot.adapters import Event
from nonebot.params import ShellCommandArgs
from nonebot.plugin import require
require("nonebot_plugin_alconna")
from nonebot_plugin_alconna import UniMessage

from .backend.comfyui import ComfyuiUI
from .backend.utils import run_later


async def get_message_at(data: str) -> int:
    '''
    获取at列表
    :param data: event.json()
    '''
    data = json.loads(data)
    try:
        msg = data['original_message'][1]
        if msg['type'] == 'at':
            return int(msg['data']['qq'])
    except Exception:
        return None


async def comfyui_handler(bot: Bot, event: Event, args: Namespace = ShellCommandArgs()):

    comfyui_instance = ComfyuiUI(**vars(args), nb_event=event, args=args, bot=bot)

    img_url = []
    reply = event.reply
    at_id = await get_message_at(event.json())
    # 获取图片url
    if at_id and not reply:
        img_url = [f"https://q1.qlogo.cn/g?b=qq&nk={at_id}&s=640"]
    for seg in event.message['image']:
        img_url.append(seg.data["url"])
    if reply:
        for seg in reply.message['image']:
            img_url.append(seg.data["url"])

    image_byte = []
    if img_url:
        for url in img_url:
            url = url.replace("gchat.qpic.cn", "multimedia.nt.qq.com.cn")

            async with aiohttp.ClientSession() as session:
                logger.info(f"检测到图片，自动切换到以图生图，正在获取图片")
                async with session.get(url) as resp:
                    image_byte.append(await resp.read())

        comfyui_instance.init_images = image_byte

    await run_later(UniMessage.text(f"已选择工作流: {comfyui_instance.work_flows}, 正在生成, 请稍等.").send(), 2)

    await comfyui_instance.select_backend()
    await comfyui_instance.posting()

    unimsg: UniMessage = comfyui_instance.unimessage
    unimsg = UniMessage.text('生成完毕') + unimsg

    await unimsg.send(reply_to=True)
    if comfyui_instance.multimedia_unimsg:
        await comfyui_instance.multimedia_unimsg.send()


