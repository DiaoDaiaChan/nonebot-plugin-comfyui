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
from ..config import config

from io import BytesIO
from PIL import Image
from asyncio import get_running_loop
from nonebot_plugin_alconna import UniMessage

cd = {}
daily_calls = {}
PLUGIN_VERSION = '0.6.0'

async def run_later(func, delay=1):
    loop = get_running_loop()
    loop.call_later(
        delay,
        lambda: loop.create_task(
            func
        )
    )


async def set_res(new_img: Image) -> str:
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
            from ..config import wd_instance
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
    
    shape = config.comfyui_shape_preset
    shape_str = ''
    for k, v in shape.items():
        shape_str += f"预设: {k}, 分辨率: {v[0]}x{v[1]}"
    

    help_text = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ComfyUI 绘图插件文档 - Version {PLUGIN_VERSION}</title>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Segoe UI', system-ui, sans-serif;
            line-height: 1.6;
            color: #2c3e50;
            background: #f8f9fa;
            padding: 2rem;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 15px rgba(0,0,0,0.1);
            padding: 2rem;
        }}

        h1, h2, h3 {{
            color: #2c3e50;
            margin-bottom: 1.5rem;
        }}

        h1 {{
            font-size: 2.5rem;
            border-bottom: 3px solid #3498db;
            padding-bottom: 0.5rem;
            margin-bottom: 2rem;
        }}

        h2 {{
            font-size: 1.8rem;
            color: #34495e;
            margin-top: 2rem;
            padding-left: 1rem;
            border-left: 4px solid #3498db;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1.5rem 0;
            background: white;
        }}

        th, td {{
            padding: 12px 15px;
            border: 1px solid #ecf0f1;
            text-align: left;
        }}

        th {{
            background-color: #3498db;
            color: white;
            font-weight: 600;
        }}

        tr:nth-child(even) 
            background-color: #f8f9fa;
        }}

        code {{
            font-family: 'Fira Code', monospace;
            background: #2c3e50;
            color: #ecf0f1;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.9em;
        }}

        pre {{
            background: #2c3e50;
            color: #ecf0f1;
            padding: 1rem;
            border-radius: 8px;
            overflow-x: auto;
            margin: 1rem 0;
            line-height: 1.4;
        }}

        .command-table {{
            margin: 2rem 0;
        }}

        .param-table td:nth-child(1) {{
            width: 120px;
            font-weight: 500;
            color: #e67e22;
        }}

        .warning {{
            color: #e74c3c;
            padding: 1rem;
            background: #fdeded;
            border-radius: 6px;
            margin: 1rem 0;
        }}

        .example {{
            position: relative;
            margin: 1.5rem 0;
        }}

        .example::before {{
            content: "🖼️ 示例";
            display: block;
            color: #3498db;
            font-weight: bold;
            margin-bottom: 0.5rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎨 ComfyUI 绘图插件文档</h1>

        <section class="basic-commands">
            <h2>基础命令</h2>
            <div class="warning">
                ⚠️ 默认不支持中文提示词，必须包含至少1个正向提示词
                ⚠️ 提示词中如果包含单引号, 需要用双引号括起来, 例如 prompt "girl's"
            </div>
            
            <pre><code>prompt [正面提示词] [参数]</code></pre>
            <pre><code>查看工作流 ,  查看工作流 flux (查看带有flux的工作流), 查看工作流 1 查看1号工作流(按顺序)</code></pre>

            <h3>核心参数表</h3>
            <table class="param-table">
                <tr>
                    <th>参数</th>
                    <th>类型</th>
                    <th>说明</th>
                    <th>默认值</th>
                </tr>
                <tr>
                    <td>-u</td>
                    <td>str/td>
                    <td>负面提示词</td>
                    <td>无</td>
                </tr>
                <tr>
                    <td>--ar</td>
                    <td>str</td>
                    <td>画幅比例 (如 16:9)</td>
                    <td>1:1</td>
                </tr>
                <tr>
                    <td>-s</td>
                    <td>int</td>
                    <td>种子</td>
                    <td>随机整数</td>
                </tr>
                                <tr>
                    <td>-t</td>
                    <td>int</td>
                    <td>迭代步数</td>
                    <td>28</td>
                </tr>
                                <tr>
                    <td>--cfg</td>
                    <td>float</td>
                    <td>CFG scale</td>
                    <td>7.0</td>
                </tr>
                                <tr>
                    <td>-n</td>
                    <td>float</td>
                    <td>去噪强度</td>
                    <td>1.0</td>
                </tr>
                                <tr>
                    <td>-高</td>
                    <td>int</td>
                    <td>图像高度</td>
                    <td>1216</td>
                </tr>
                                <tr>
                    <td>-宽</td>
                    <td>int</td>
                    <td>图像宽度</td>
                    <td>832</td>
                </tr>
                                <tr>
                    <td>-wf</td>
                    <td>str</td>
                    <td>选择工作流</td>
                    <td>None</td>
                </tr>
                                <tr>
                    <td>-sp</td>
                    <td>str</td>
                    <td>采样器</td>
                    <td>euler</td>
                </tr>
                <tr>
                    <td>-sch</td>
                    <td>str</td>
                    <td>调度器</td>
                    <td>normal</td>
                </tr>
                                <tr>
                    <td>-b</td>
                    <td>int</td>
                    <td>每批数量</td>
                    <td>1</td>
                </tr>
                                <tr>
                    <td>-bc</td>
                    <td>int</td>
                    <td>生成几批</td>
                    <td>1</td>
                </tr>
                                <tr>
                    <td>-m</td>
                    <td>str</td>
                    <td>模型</td>
                    <td>None</td>
                </tr>
                                <tr>
                    <td>-o</td>
                    <td>bool</td>
                    <td>不使用内置正面提示词</td>
                    <td>False</td>
                </tr>
                                <tr>
                    <td>-on</td>
                    <td>bool</td>
                    <td>不使用内置负面提示词</td>
                    <td>False</td>
                </tr>
                                <tr>
                    <td>-be</td>
                    <td>str</td>
                    <td>选择指定的后端索引(从0开始)/url</td>
                    <td>0</td>
                </tr>
                                                <tr>
                    <td>-f</td>
                    <td>bool</td>
                    <td>发送为转发消息</td>
                    <td>False</td>
                </tr>
                                                <tr>
                    <td>-gif</td>
                    <td>bool</td>
                    <td>将gif图片输入工作流</td>
                    <td>False</td>
                </tr>
                                                <tr>
                    <td>-con</td>
                    <td>bool</td>
                    <td>并发生图</td>
                    <td>False</td>
                <tr>
                    <td>-shape</td>
                    <td>str</td>
                    <td>使用预设分辨率, 有{shape_str}</td>
                    <td>False</td>
                </tr>
                </tr>
            </table>5
        </section>

        <section class="advanced-commands">
            <h2>高级命令</h2>
            <h3>注册命令列表</h3>
            <pre><code>{'<br>'.join(reg_command) if reg_command else '暂未注册额外命令'}</code></pre>

            <div class="command-table">
                <h3>完整参数示例</h3>
                <pre><code>prompt "a girl, masterpiece, 8k" -u "badhand, blurry" --ar 3:4 -s 123456 --steps 25 --cfg 7.5 -高 768 -宽 512</code></pre>
            </div>
        </section>

        <section class="queue-management">
            <h2>队列管理命令 - queue</h2>
            <table>
                <tr>
                    <td><code>-get</code></td>
                    <td>后接任务的id/URL</td>
                    <td><code>queue -get ... -be 0</code></td>
                </tr>
                <tr>
                    <td><code>-be</code></td>
                    <td>指定后端索引/URL</td>
                    <td><code>queue -get ... -be 0</code></td>
                </tr>
                                <tr>
                    <td><code>-t</code></td>
                    <td>追踪后端当前所有的任务id/URL</td>
                    <td><code>queue -be 0 -t ....</code></td>
                </tr>
                                <tr>
                    <td><code>-d</code></td>
                    <td>需要删除的任务id/URL</td>
                    <td><code>queue -d ... -be 0</code></td>
                </tr>
                                <tr>
                    <td><code>-c</code></td>
                    <td>清除后端上的所有任务/URL</td>
                    <td><code>queue -c ... -be 0</code></td>
                </tr>
                                <tr>
                    <td><code>-i</code></td>
                    <td>需要查询的任务id/URL</td>
                    <td><code>queue -i ... -be 0</code></td>
                </tr>
                                <tr>
                    <td><code>-v</code></td>
                    <td>查看历史任务, 配合-index使用/URL</td>
                    <td><code>queue -v -index 0-20 -be 0 (获取前20个任务id)
</code></td>
                </tr>
                                <tr>
                    <td><code>-stop</code></td>
                    <td>停止当前生成/URL</td>
                    <td><code>queue -stop -be 0</code></td>
                </tr>
            </table>
        </section>
        
        <section class="queue-management">
            <h2>查询后端节点 - capi</h2>
            <table>
                <tr>
                    <td><code>-get</code></td>
                    <td>需要查看的节点信息, 例如 capi -get all -be 0 (获取所有节点名称)</td>
                    <td><code>capi -get "KSampler" -be 0 (获取KSampler节点的信息)</code></td>
                </tr>
                <tr>
                    <td><code>-be</code></td>
                    <td>指定后端索引/URL</td>
                    <td><code>capi -get ... -be 0</code></td>
                </tr>
            </table>
        </section>

        <footer>
            <p><strong>By:</strong> nonebot-plugin-comfyui</p>
        </footer>
    </div>
</body>
</html>
"""
    return help_text


