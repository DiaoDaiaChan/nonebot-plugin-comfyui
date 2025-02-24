import os
import json
import base64
import asyncio
import random
import nonebot
import traceback
import aiohttp
import filetype

from nonebot import logger
from ..config import config, PLUGIN_DIR

from io import BytesIO
from PIL import Image
from asyncio import get_running_loop
from nonebot_plugin_alconna import UniMessage
from jinja2 import Environment, FileSystemLoader

cd = {}
daily_calls = {}
PLUGIN_VERSION = '0.7'


async def run_later(func, delay=1):
    loop = get_running_loop()
    loop.call_later(
        delay,
        lambda: loop.create_task(
            func
        )
    )


async def set_res(new_img: Image) -> str:
    if config.comfyui_audit_comp:
        max_res = 640
        old_res = new_img.width * new_img.height
        width = new_img.width
        height = new_img.height

        if old_res > pow(max_res, 2):
            if width <= height:
                ratio = height / width
                width: float = max_res / pow(ratio, 0.5)
                height: float = width * ratio
            else:
                ratio = width / height
                height: float = max_res / pow(ratio, 0.5)
                width: float = height * ratio
            logger.info(f"审核图片尺寸已调整至{round(width)}x{round(height)}")
            new_img.resize((round(width), round(height)))

    img_bytes = BytesIO()
    new_img.save(img_bytes, format="JPEG")
    img_bytes = img_bytes.getvalue()
    img_base64 = base64.b64encode(img_bytes).decode("utf-8")
    return img_base64


async def pic_audit_standalone(
        img_base64,
        is_return_tags=False,
        audit=False,
        return_bool=False
):

    byte_img = (
        img_base64 if isinstance(img_base64, bytes)
        else base64.b64decode(img_base64)
    )
    img = Image.open(BytesIO(byte_img)).convert("RGB")
    img_base64 = await set_res(img)

    async def get_caption(payload):

        if config.comfyui_audit_local:
            from .wd_audit import tagger_main
            from .. import wd_instance
            resp_dict = {}
            caption = await asyncio.get_event_loop().run_in_executor(
                None,
                tagger_main,
                payload['image'],
                payload['threshold'],
                wd_instance
            )
            resp_dict["caption"] = caption
            return resp_dict

        else:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                        url=f"{config.comfyui_audit_site}/tagger/v1/interrogate",
                        json=payload
                ) as resp:

                    if resp.status not in [200, 201]:
                        resp_text = await resp.text()
                        logger.error(f"API失败，错误信息:{resp.status, resp_text}")
                        return None
                    resp_dict = await resp.json()
                    return resp_dict

    payload = {"image": img_base64, "model": "wd14-vit-v2-git", "threshold": 0.35}
    resp_dict = await get_caption(payload)

    tags = resp_dict["caption"]
    replace_list = ["general", "sensitive", "questionable", "explicit"]
    to_user_list = ["这张图很安全!", "较为安全", "色情", "泰色辣!"]
    possibilities = {}
    to_user_dict = {}
    message = "这是审核结果:\n"

    for i, to_user in zip(replace_list, to_user_list):
        possibilities[i] = tags[i]
        percent = f":{tags[i] * 100:.2f}".rjust(6)
        message += f"[{to_user}{percent}%]\n"
        to_user_dict[to_user] = tags[i]

    value = list(to_user_dict.values())
    value.sort(reverse=True)
    reverse_dict = {value: key for key, value in to_user_dict.items()}
    message += f"最终结果为:{reverse_dict[value[0]].rjust(5)}"

    if return_bool:
        value = list(possibilities.values())
        value.sort(reverse=True)
        reverse_dict = {value: key for key, value in possibilities.items()}
        logger.info(message)
        if config.comfyui_audit_level == 1:
            return True if reverse_dict[value[0]] == "explicit" else False
        elif config.comfyui_audit_level == 2:
            return True if reverse_dict[value[0]] == "questionable" or reverse_dict[value[0]] == "explicit" else False
        elif config.comfyui_audit_level == 3:
            return True if (
                    reverse_dict[value[0]] == "questionable" or
                    reverse_dict[value[0]] == "explicit" or
                    reverse_dict[value[0]] == "sensitive"
            ) else False
        elif config.comfyui_audit_level == 100:
            return True

    if is_return_tags:
        return message, tags
    if audit:
        return possibilities, message
    return message


async def send_msg_and_revoke(message: UniMessage | str, reply_to=False, r=None):
    if isinstance(message, str):
        message = UniMessage(message)

    async def main(message, reply_to, r):
        if r:
            await revoke_msg(r)
        else:
            r = await message.send(reply_to=reply_to)
            await revoke_msg(r)
        return

    await run_later(main(message, reply_to, r), 2)


async def revoke_msg(r, time=None, bot=None):
    if isinstance(r, str):
        if bot is None:
            bot = nonebot.get_bot()
        await bot.delete_msg(message_id=r)
    else:
        await r.recall(delay=time or random.randint(60, 100), index=0)


async def get_message_at(data: str) -> int | None:
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


def extract_first_frame_from_gif(gif_bytes):
    gif_image = Image.open(BytesIO(gif_bytes))

    gif_image.seek(0)
    first_frame = gif_image.copy()

    byte_array = BytesIO()
    first_frame.save(byte_array, format="PNG")
    return byte_array.getvalue()


async def get_image(event, gif) -> list[bytes]:
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
        from . import ComfyUI
        for url in img_url:
            url = url.replace("gchat.qpic.cn", "multimedia.nt.qq.com.cn")
            logger.info(f"检测到图片，自动切换到以图生图，正在获取图片")

            byte_image = await ComfyUI.http_request("GET", url, format=False)

            kind = filetype.guess(byte_image)
            file_format = kind.extension if kind else "unknown"

            if not gif:
                if 'gif' in file_format:
                    byte_image = extract_first_frame_from_gif(byte_image)
                else:
                    pass
            else:
                pass

            image_byte.append(byte_image)

    return image_byte


async def comfyui_generate(event, bot, args):
    from . import ComfyUI
    comfyui_instance = ComfyUI(**vars(args), nb_event=event, args=args, bot=bot)
    # 加载图片
    image_byte = await get_image(event, args.gif)
    comfyui_instance.init_images = image_byte

    try:
        await comfyui_instance.exec_generate()
    except Exception as e:
        traceback.print_exc()
        await send_msg_and_revoke(f'任务{comfyui_instance.task_id}生成失败, {e}')
        raise e

    unimsg: UniMessage = comfyui_instance.unimessage
    unimsg = UniMessage.text(f'队列完成, 耗时:{comfyui_instance.spend_time}秒\n') + unimsg
    comfyui_instance.unimessage = unimsg

    await comfyui_instance.send_all_msg()

    return comfyui_instance


async def get_file_url(comfyui_instance, outputs, backend_url, task_id):
    images_url = []
    video_url = []
    audio_url = []

    for imgs in list(outputs.values()):
        if 'images' in imgs:
            for img in imgs['images']:

                filename = img['filename']
                _, file_format = os.path.splitext(filename)

                if img['subfolder'] == "":
                    url = f"{backend_url}/view?filename={filename}"
                else:
                    url = f"{backend_url}/view?filename={filename}&subfolder={img['subfolder']}"

                if img['type'] == "temp":
                    url = f"{backend_url}/view?filename={filename}&subfolder=&type=temp"

                images_url.append({"url": url, "file_format": file_format})

        if 'gifs' in imgs:
            for img in imgs['gifs']:
                filename = img['filename']
                _, file_format = os.path.splitext(filename)

                if img['subfolder'] == "":
                    url = f"{backend_url}/view?filename={filename}"
                else:
                    url = f"{backend_url}/view?filename={filename}&subfolder={img['subfolder']}"

                if img['type'] == "temp":
                    url = f"{backend_url}/view?filename={filename}&subfolder=&type=temp"

                video_url.append({"url": url, "file_format": file_format})

        if "audio" in imgs:
            for img in imgs['audio']:
                filename = img['filename']
                _, file_format = os.path.splitext(filename)

                if img['subfolder'] == "":
                    url = f"{backend_url}/view?filename={filename}"
                else:
                    url = f"{backend_url}/view?filename={filename}&subfolder={img['subfolder']}"

                if img['type'] == "temp":
                    url = f"{backend_url}/view?filename={filename}&subfolder=&type=temp"

                audio_url.append({"url": url, "file_format": file_format})

        if 'text' in imgs:

            for img in imgs['text']:
                comfyui_instance.unimessage += img

    comfyui_instance.resp_msg.media_url['image'] = images_url
    comfyui_instance.resp_msg.media_url['video'] = video_url
    comfyui_instance.resp_msg.media_url['audio'] = audio_url
    comfyui_instance.resp_msg.backend_index = config.comfyui_url_list.index(backend_url)
    comfyui_instance.resp_msg.task_id = task_id

    comfyui_instance.resp_msg_list.append(comfyui_instance.resp_msg)

    return comfyui_instance


async def build_help_text(reg_command):
        
    template_data = {
        "reg_commands": reg_command,
        "parameters": [
            {"flag": "-u", "description": "负面提示词", "example": "prompt -u '低质量'"},
            {"flag": "--ar", "description": "画幅比例", "example": "prompt --ar 16:9"},
            {"flag": "-s", "description": "种子", "example": "prompt -s 12345"},
            {"flag": "--steps", "description": "采样步数", "example": "prompt --steps 50"},
            {"flag": "--cfg", "description": "CFG scale", "example": "prompt --cfg 7.5"},
            {"flag": "-n", "description": "去噪强度", "example": "prompt -n 0.75"},
            {"flag": "-高", "description": "高度", "example": "prompt -高 512"},
            {"flag": "-宽", "description": "宽度", "example": "prompt -宽 768"},
            {"flag": "-wf", "description": "工作流", "example": "prompt -wf workflow"},
            {"flag": "-sp", "description": "采样器", "example": "prompt -sp euler_a"},
            {"flag": "-sch", "description": "调度器", "example": "prompt -sch karras"},
            {"flag": "-b", "description": "每批数量(一次生成几张)", "example": "prompt -b 2"},
            {"flag": "-bc", "description": "生成几批(生成几次)", "example": "prompt -bc 4"},
            {"flag": "-m", "description": "模型", "example": "prompt -m model.ckpt"},
            {"flag": "-o", "description": "不使用内置正面提示词", "example": "prompt -o"},
            {"flag": "-on", "description": "不使用内置负面提示词", "example": "prompt -on"},
            {"flag": "-be", "description": "选择指定的后端索引(从0开始)/url", "example": "prompt -be 1"},
            {"flag": "-f", "description": "发送为转发消息", "example": "prompt -f"},
            {"flag": "-gif", "description": "将gif图片输入工作流", "example": "prompt -gif"},
            {"flag": "-con", "description": "并发使用多后端生图, 和-bc一起使用", "example": "prompt -con -bc 3"},
            {"flag": "-r", "description": "自定义的比例字符串, 可以在画幅预设中查看", "example": "prompt -r 512x512 / prompt -r p"},
        ],
        "shape_presets": [
            {"name": k, "width": v[0], "height": v[1]} 
            for k, v in config.comfyui_shape_preset.items()
        ],
        "queue_params": [
            {
                "flag": "-be",
                "description": "需要查看队列的后端索引或者URL(不添加默认0)",
                "example": "queue -get bedadef6-269c-43f4-9be4-0e5b07061233 -be 0"
            },
            {
                "flag": "-t",
                "description": "追踪后端当前所有的任务id",
                "example": "queue -t -be 'http://127.0.0.1:8288'"
            },
            {
                "flag": "-d",
                "description": "需要删除的任务id",
                "example": "queue -d bedadef6-269c-43f4-9be4-0e5b07061233 -be 0"
            },
            {
                "flag": "-c",
                "description": "清除后端上的所有任务",
                "example": "queue -c -be 0"
            },
            {
                "flag": "-i",
                "description": "需要查询的任务id",
                "example": "queue -i bedadef6-269c-43f4-9be4-0e5b07061233 -be 0"
            },
            {
                "flag": "-v",
                "description": "查看历史任务, 配合-index使用",
                "example": "queue -v -index 0-20 -be 0"
            },
            {
                "flag": "-get",
                "description": "后接任务的id",
                "example": "queue -get bedadef6-269c-43f4-9be4-0e5b07061233 -be 0"
            },
            {
                "flag": "-stop",
                "description": "停止当前生成",
                "example": "queue -stop"
            }
        ],
        "capi_params": [
            {
                "flag": "-be",
                "description": "需要查看节点的后端索引或者URL(不添加默认0)",
                "example": "capi -be 0 -get all"
            },
            {
                "flag": "-get",
                "description": "需需要查看的节点信息, 例如 capi -get all -be 0 (获取所有节点名称)",
                "example": "capi -get KSampler -be 0 (获取KSampler节点的信息)"
            }
        ],
        "version": PLUGIN_VERSION
    }

    env = Environment(loader=FileSystemLoader(str(PLUGIN_DIR / 'template')))
    template = env.get_template('help.html')
    return template.render(**template_data)


def get_and_filter_work_flows(search=None, index=None) -> list:

    index = int(index) if index else None

    if not isinstance(search, str):
        search = None

    wf_files = []
    for root, dirs, files in os.walk(config.comfyui_workflows_dir):
        for file in files:
            if file.endswith('.json') and not file.endswith('_reflex.json'):
                if search and search in file:
                    wf_files.append(file.replace('.json', ''))
                elif not search:
                    wf_files.append(file.replace('.json', ''))

    if index is not None:
        if 1 <= index < len(wf_files) + 1:
            return [wf_files[index-1]]
        else:
            return []

    return wf_files