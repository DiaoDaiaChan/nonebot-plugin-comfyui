import copy
import json
import random
import uuid
import os
import re

import aiofiles
import aiohttp
import asyncio
import hashlib
import ssl

import nonebot
from tqdm import tqdm
from nonebot import logger
from nonebot.adapters import Event
from typing import Union, Optional
from argparse import Namespace
from pathlib import Path
from datetime import datetime
from aiohttp import ClientSession, TCPConnector

from ..config import config
from ..handler import UniMessage
from .utils import pic_audit_standalone, run_later

MAX_SEED = 2 ** 32
OTHER_ACTION = {"override", "note", "presets", "media", "command", "reg_args"}


class AllComfyuiTask:

    all_task_dict: dict = {}
    user_task: dict = {}

    def __init__(self, user_id: str, event: Event):

        self.user_id = user_id
        self.event = event
        self.task_id = None


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


class ComfyUIQueue:
    def __init__(self, queue_size=10):
        self.queue = asyncio.Queue(maxsize=queue_size)
        self.semaphore = asyncio.Semaphore(queue_size)


class ComfyuiUI:
    work_flows_init: list = get_and_filter_work_flows()

    @classmethod
    def update_wf(cls, search=None, index=None):
        cls.work_flows_init = get_and_filter_work_flows(search, index=index)
        return cls.work_flows_init

    def __init__(
            self,
            nb_event: Event,
            args: Namespace,
            bot: nonebot.Bot,
            prompt: str = None,
            negative_prompt: str = None,
            accept_ratio: str = None,
            seed: Optional[int] = None,
            steps: Optional[int] = None,
            cfg_scale: Optional[float] = None,
            denoise_strength: Optional[float] = None,
            height: Optional[int] = None,
            width: Optional[int] = None,
            video: Optional[bool] = None,
            work_flows: str = None,
            sampler: Optional[str] = None,
            scheduler: Optional[str] = None,
            batch_size: Optional[int] = None,
            model: Optional[str] = None,
            override: Optional[bool] = False,
            override_ng: Optional[bool] = False,
            backend: Optional[str] = None,
            batch_count: Optional[int] = None,
            **kwargs
    ):

        # 映射参数相关
        self.reflex_dict = {'sampler': {
            "DPM++ 2M": "dpmpp_2m",
            "DPM++ SDE": "dpmpp_sde",
            "DPM++ 2M SDE": "dpmpp_2m_sde",
            "DPM++ 2M SDE Heun": "dpmpp_2m_sde",
            "DPM++ 2S a": "dpmpp_2s_ancestral",
            "DPM++ 3M SDE": "dpmpp_3m_sde",
            "Euler a": "euler_ancestral",
            "Euler": "euler",
            "LMS": "lms",
            "Heun": "heun",
            "DPM2": "dpm_2",
            "DPM2 a": "dpm_2_ancestral",
            "DPM fast": "dpm_fast",
            "DPM adaptive": "dpm_adaptive",
            "Restart": "restart",
            "HeunPP2": "heunpp2",
            "IPNDM": "ipndm",
            "IPNDM_V": "ipndm_v",
            "DEIS": "deis",
            "DDIM": "ddim",
            "DDIM CFG++": "ddim",
            "PLMS": "plms",
            "UniPC": "uni_pc",
            "LCM": "lcm",
            "DDPM": "ddpm",
        }, 'scheduler': {
            "Automatic": "normal",
            "Karras": "karras",
            "Exponential": "exponential",
            "SGM Uniform": "sgm_uniform",
            "Simple": "simple",
            "Normal": "normal",
            "ddDDIM": "ddim_uniform",
            "Beta": "beta"
        }
        }

        self.work_flows = None

        # ComfyuiAPI相关
        if work_flows is None:
            work_flows = config.comfyui_default_workflows

        for wf in self.update_wf(index=work_flows if work_flows.strip().isdigit() else None):

            if len(self.work_flows_init) == 1:
                self.work_flows = self.work_flows_init[0]

            else:
                if work_flows in wf:
                    self.work_flows = wf
                    break
                else:
                    self.work_flows = "txt2img"

        logger.info(f"选择工作流: {self.work_flows}")

        # 必要参数
        self.nb_event = nb_event
        self.args = args
        self.bot = bot

        # 绘图参数相关
        self.prompt: str = self.list_to_str(prompt or "")
        self.negative_prompt: str = self.list_to_str(negative_prompt or "")
        self.accept_ratio: str = accept_ratio
        if self.accept_ratio is None:
            self.height: int = height or 1216
            self.width: int = width or 832
        else:
            self.width, self.height = self.extract_ratio()
        self.seed: int = seed or random.randint(0, 2 ^ 32)
        self.steps: int = steps or 20
        self.cfg_scale: float = cfg_scale or 7.0
        self.denoise_strength: float = denoise_strength or 1.0

        self.sampler: str = (
            self.reflex_dict['sampler'].get(sampler, "dpmpp_2m") if
            sampler not in self.reflex_dict['sampler'].values() else
            sampler or "dpmpp_2m"
        )
        self.scheduler: str = (
            self.reflex_dict['scheduler'].get(scheduler, "normal") if
            scheduler not in self.reflex_dict['scheduler'].values() else
            scheduler or "karras"
        )

        self.batch_size: int = batch_size or 1
        self.batch_count: int = batch_count or 1
        self.total_count: int = self.batch_count * self.batch_size
        self.model: str = model or config.comfyui_model
        self.override = override
        self.override_ng = override_ng

        self.comfyui_api_json = None
        self.reflex_json = None
        self.override_backend_setting_dict: dict = {}

        self.selected_backend = backend
        if backend is not None and backend.isdigit():
            self.backend_url = config.comfyui_url_list[int(backend)]
        else:
            self.backend_url = backend

        self.backend_url: str = self.backend_url if backend else config.comfyui_url

        # 用户相关
        self.client_id = uuid.uuid4().hex
        self.user_id = self.nb_event.get_user_id()
        self.task_id = None
        self.adapters = nonebot.get_adapters()

        # 流媒体相关
        self.init_images: list[bytes] = []
        self.media_url: list = []
        self.unimessage: UniMessage = UniMessage.text("")
        self.multimedia_unimsg: UniMessage | None = None
        self.media_type: str = 'video' if video else 'image'
        self.file_format: str = '.png'

    async def get_workflows_json(self):
        async with aiofiles.open(
                f"{config.comfyui_workflows_dir}/{self.work_flows}.json",
                'r',
                encoding='utf-8'
        ) as f:
            self.comfyui_api_json = json.loads(await f.read())

        async with aiofiles.open(
                f"{config.comfyui_workflows_dir}/{self.work_flows}_reflex.json",
                'r',
                encoding='utf-8'
        ) as f:
            self.reflex_json = json.loads(await f.read())

    def extract_ratio(self):
        """
        提取宽高比为分辨率
        """
        if ":" in self.accept_ratio:
            width_ratio, height_ratio = map(int, self.accept_ratio.split(':'))
        else:
            return 768, 1152

        total_pixels = config.comfyui_base_res ** 2
        aspect_ratio = width_ratio / height_ratio

        if aspect_ratio >= 1:
            width = int((total_pixels * aspect_ratio) ** 0.5)
            height = int(width / aspect_ratio)
        else:
            height = int((total_pixels / aspect_ratio) ** 0.5)
            width = int(height * aspect_ratio)

        return width, height

    async def update_api_json(self, init_images):
        api_json = copy.deepcopy(self.comfyui_api_json)
        raw_api_json = copy.deepcopy(self.comfyui_api_json)

        update_mapping = {
            "sampler": {
                "seed": self.seed,
                "steps": self.steps,
                "cfg": self.cfg_scale,
                "sampler_name": self.sampler,
                "scheduler": self.scheduler,
                "denoise": self.denoise_strength
            },
            "seed": {
                "seed": self.seed,
                "noise_seed": self.seed
            },
            "image_size": {
                "width": self.width,
                "height": self.height,
                "batch_size": self.batch_size
            },
            "prompt": {
                "text": self.prompt
            },
            "negative_prompt": {
                "text": self.negative_prompt
            },
            "checkpoint": {
                "ckpt_name": self.model if self.model else None,
                "unet_name": self.model if self.model else None
            },
            "load_image": {
                "image": init_images[0]['name'] if self.init_images else None
            },
            "tipo": {
                "width": self.width,
                "height": self.height,
                "seed": self.seed,
                "tags": self.prompt,
            }
        }

        __OVERRIDE_SUPPORT_KEYS__ = {
            'keep',
            'value',
            'append_prompt',
            'append_negative_prompt',
            'remove',
            "randint",
            "get_text",
            "upscale",
            'image'
        }
        __ALL_SUPPORT_NODE__ = set(update_mapping.keys())

        for item, node_id in self.reflex_json.items():

            if node_id and item not in OTHER_ACTION:

                org_node_id = node_id

                if isinstance(node_id, list):
                    node_id = node_id
                elif isinstance(node_id, int or str):
                    node_id = [node_id]
                elif isinstance(node_id, dict):
                    node_id = list(node_id.keys())

                for id_ in node_id:
                    id_ = str(id_)
                    update_dict = api_json.get(id_, None)
                    if update_dict and item in update_mapping:
                        api_json[id_]['inputs'].update(update_mapping[item])

                if isinstance(org_node_id, dict):
                    for node, override_dict in org_node_id.items():
                        single_node_or = override_dict.get("override", {})

                        if single_node_or:
                            for key, override_action in single_node_or.items():

                                if override_action == "randint":
                                    api_json[node]['inputs'][key] = random.randint(0, MAX_SEED)

                                elif override_action == "keep":
                                    org_cons = raw_api_json[node]['inputs'][key]

                                elif override_action == "append_prompt" and self.override is False:
                                    prompt = raw_api_json[node]['inputs'][key]
                                    prompt = self.prompt + prompt
                                    api_json[node]['inputs'][key] = prompt

                                elif override_action == "append_negative_prompt" and self.override_ng is False:
                                    prompt = raw_api_json[node]['inputs'][key]
                                    prompt = self.negative_prompt + prompt
                                    api_json[node]['inputs'][key] = prompt

                                elif "upscale" in override_action:
                                    scale = 1.5
                                    if "_" in override_action:
                                        scale = float(override_action.split("_")[1])

                                    if key == 'width':
                                        res = self.width
                                    elif key == 'height':
                                        res = self.height

                                    upscale_size = int(res * scale)
                                    api_json[node]['inputs'][key] = upscale_size

                                elif "value" in override_action:
                                        override_value = raw_api_json[node]['inputs'][key]
                                        if "_" in override_action:
                                            override_value = override_action.split("_")[1]
                                            override_type = override_action.split("_")[2]
                                            if override_type == "int":
                                                override_value = int(override_value)
                                            elif override_type == "float":
                                                override_value = float(override_value)
                                            elif override_type == "str":
                                                override_value = str(override_value)

                                        api_json[node]['inputs'][key] = override_value

                                elif "image" in override_action:
                                    image_id = int(override_action.split("_")[1])
                                    api_json[node]['inputs'][key] = init_images[image_id]['name']

                        else:
                            update_dict = api_json.get(node, None)
                            if update_dict and item in update_mapping:
                                api_json[node]['inputs'].update(update_mapping[item])

            else:
                if item == "media":
                    self.media_type = node_id

                elif item == "reg_args":
                    reg_args = node_id
                    for node, item_ in reg_args.items():
                        for arg in item_["args"]:

                            args_dict = vars(self.args)
                            org_key = arg["dest"]
                            args_key = None

                            if "dest_to_value" in arg:
                                json_key = arg["dest_to_value"][arg["dest"]]
                                args_key = list(arg["dest_to_value"].keys())[0]

                            else:
                                json_key = arg['dest']

                            update_node = {}

                            if hasattr(self.args, org_key):
                                get_value = args_key if args_key else json_key
                                update_node[json_key] = args_dict[get_value]

                            api_json[node]['inputs'].update(update_node)

        await run_later(self.compare_dicts(api_json, self.comfyui_api_json), 0.5)
        self.comfyui_api_json = api_json

    async def heart_beat(self, id_):
        logger.info(f"{id_} 开始请求")

        async def get_images():

            response: dict = await self.http_request(
                method="GET",
                target_url=f"{self.backend_url}/history/{id_}",
            )

            try:
                if self.media_type == 'image':
                    for img in response[id_]['outputs'][str(self.reflex_json.get('output', 9))]['images']:
                        filename = img['filename']
                        _, self.file_format = os.path.splitext(filename)

                        if img['subfolder'] == "":
                            url = f"{self.backend_url}/view?filename={filename}"
                        else:
                            url = f"{self.backend_url}/view?filename={filename}&subfolder={img['subfolder']}"

                        self.media_url.append(url)

                elif self.media_type == 'video':
                    for img in response[id_]['outputs'][str(self.reflex_json.get('output', 9))]['gifs']:
                        filename = img['filename']
                        _, self.file_format = os.path.splitext(filename)

                        if img['subfolder'] == "":
                            url = f"{self.backend_url}/view?filename={filename}"
                        else:
                            url = f"{self.backend_url}/view?filename={filename}&subfolder={img['subfolder']}"

                        self.media_url.append(url)

                elif self.media_type == 'audio':
                    pass

                elif self.media_type == 'text':
                    for text in response[id_]['outputs'][str(self.reflex_json.get('output', 9))]['text']:
                        self.unimessage += UniMessage.text(text)

            except KeyError:
                logger.error(f"输出节点错误!请检查reflex json中的设置!!!")

        async with aiohttp.ClientSession() as session:
            ws_url = f'{self.backend_url}/ws?clientId={self.client_id}'
            async with session.ws_connect(ws_url) as ws:

                logger.info(f"WS连接成功: {ws_url}")
                progress_bar = None

                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        ws_msg = json.loads(msg.data)

                        if ws_msg['type'] == 'progress':
                            value = ws_msg['data']['value']
                            max_value = ws_msg['data']['max']

                            if progress_bar is None:
                                progress_bar = await asyncio.to_thread(
                                    tqdm, total=max_value,
                                   desc=f"Prompt ID: {ws_msg['data']['prompt_id']}",
                                   unit="steps"
                                )

                            delta = value - progress_bar.n
                            await asyncio.to_thread(progress_bar.update, delta)

                        if ws_msg['type'] == 'executing':
                            if ws_msg['data']['node'] is None:
                                logger.info(f"{id_}绘画完成!")
                                await get_images()
                                await ws.close()

                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error(f"Error: {msg.data}")
                        await ws.close()
                        break

                if progress_bar is not None:
                    await asyncio.to_thread(progress_bar.close)

    async def posting(self):

        await self.get_workflows_json()

        if self.reflex_json.get('override', None):
            self.override_backend_setting_dict = self.reflex_json['override']
            await self.override_backend_setting_func()

        upload_img_resp_list = []

        if self.init_images:
            for image in self.init_images:
                resp = await self.upload_image(image, uuid.uuid4().hex)
                upload_img_resp_list.append(resp)

        await self.update_api_json(upload_img_resp_list)

        input_ = {
            "client_id": self.client_id,
            "prompt": self.comfyui_api_json
        }

        respond = await self.http_request(
            method="POST",
            target_url=f"{self.backend_url}/prompt",
            content=json.dumps(input_)
        )

        if respond.get("error", None):
            logger.error(respond)
            self.unimessage += UniMessage.text(f"生成失败: {respond['error']}")
            await self.unimessage.finish()
            # raise RuntimeError(respond["status_code"])

        self.task_id = respond['prompt_id']

        await run_later(
            UniMessage.text(f"已选择工作流: {self.work_flows}, 正在生成, 请稍等. 任务id: {self.task_id}").send(), 1
        )

        await self.heart_beat(self.task_id)

    @staticmethod
    async def http_request(
            method,
            target_url,
            headers=None,
            params=None,
            content=None,
            format=True,
            timeout=5000,
            verify=True,
            proxy=False
    ) -> Union[dict, bytes]:

        global_ssl_context = ssl.create_default_context()
        global_ssl_context.set_ciphers('DEFAULT')
        global_ssl_context.options |= ssl.OP_NO_SSLv2
        global_ssl_context.options |= ssl.OP_NO_SSLv3
        global_ssl_context.options |= ssl.OP_NO_TLSv1
        global_ssl_context.options |= ssl.OP_NO_TLSv1_1
        global_ssl_context.options |= ssl.OP_NO_COMPRESSION

        connector = TCPConnector(ssl=global_ssl_context)

        async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            async with session.request(
                    method,
                    target_url,
                    headers=headers,
                    params=params,
                    data=content,
                    ssl=verify,
            ) as response:
                if format:
                    return await response.json()
                else:
                    return await response.read()

    async def upload_image(self, image_data: bytes, name, image_type="input", overwrite=False) -> dict:

        logger.info(f"图片: {name}上传成功")

        data = aiohttp.FormData()
        data.add_field('image', image_data, filename=f"{name}.png", content_type=f'image/png')
        data.add_field('type', image_type)
        data.add_field('overwrite', str(overwrite).lower())

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.backend_url}/upload/image", data=data) as response:
                return json.loads(await response.read())

    async def download_img(self):

        image_byte = []

        for url in self.media_url:
            response = await self.http_request(
                method="GET",
                target_url=url,
                format=False
            )

            logger.info(f"图片: {url}下载成功")

            image_byte.append(response)

        if config.comfyui_save_image:
            await run_later(self.save_media(image_byte), 2)

        await self.audit_func(image_byte)

    @staticmethod
    def list_to_str(tags_list):
        tags: str = "".join([i+" " for i in tags_list if isinstance(i,str)])
        tags = re.sub("\[CQ[^\s]*?]", "", tags)
        tags = tags.replace("\\\\", "\\")
        tags = tags.split(",")
        return ','.join(tags)

    @staticmethod
    async def compare_dicts(dict1, dict2):

        modified_keys = {k for k in dict1.keys() & dict2.keys() if dict1[k] != dict2[k]}
        build_info = "节点映射情况: \n"
        for key in modified_keys:
            build_info += f"节点ID: {key} -> \n"
            for (key1, value1), (key2, value2) in zip(dict1[key].items(), dict2[key].items()):
                if value1 == value2:
                    pass
                else:
                    build_info += f"新的值: {key1} -> {value1}\n旧的值: {key2} -> {value2}\n"

        logger.info(build_info)

    async def override_backend_setting_func(self):
        """
        覆写后端设置
        """""

        for key, arg_value in vars(self.args).items():
            if hasattr(self, key):

                value = self.override_backend_setting_dict.get(key, None)

                if arg_value:
                    pass
                else:
                    if value is not None:
                        setattr(self, key, value)

    async def send_nsfw_image_to_private(self, image):

        from nonebot.adapters.onebot.v11.exception import ActionFailed

        try:
            if 'OneBot V11' in self.adapters:
                from nonebot.adapters.onebot.v11 import MessageSegment
                await self.bot.send_private_msg(user_id=self.user_id, message=MessageSegment.image(image))
            else:
                raise NotImplementedError("暂不支持其他机器人")

        except (NotImplementedError, ActionFailed, Exception) as e:
            if isinstance(NotImplementedError, e):
                logger.warning("发送失败, 暂不支持其他机器人")
            elif isinstance(ActionFailed, e):
                await UniMessage.text('图图私聊发送失败了!是不是没加机器人好友...').send()
            else:
                await UniMessage.text('图图私聊发送失败了!是不是没加机器人好友...').send()

    async def audit_func(self, image_byte):

        if self.media_type == "image":

            if 'OneBot V11' in self.adapters:
                from nonebot.adapters.onebot.v11 import PrivateMessageEvent
                if isinstance(self.nb_event, PrivateMessageEvent):
                    logger.info('私聊, 不进行审核')
                    for img in image_byte:
                        self.unimessage += UniMessage.image(raw=img)

                    return

            if config.comfyui_audit:
                task_list = []
                for img in image_byte:
                    task_list.append(pic_audit_standalone(img, return_bool=True))

                resp = await asyncio.gather(*task_list, return_exceptions=False)

                for i, img in zip(resp, image_byte):
                    if i:
                        self.unimessage += UniMessage.text("\n这张图太涩了,私聊发给你了哦!")
                        await run_later(self.send_nsfw_image_to_private(img))
                    else:
                        self.unimessage += UniMessage.image(raw=img)

            else:
                for img in image_byte:
                    self.unimessage += UniMessage.image(raw=img)

        elif self.media_type == "video":
            for video in image_byte:
                self.multimedia_unimsg = UniMessage.video(raw=video)

    async def get_backend_work_status(self, url):

        resp = await self.http_request("GET", target_url=f"{url}/queue")
        return resp

    async def select_backend(self):

        if config.comfyui_multi_backend and self.selected_backend is None:
            task_list = []
            for task in config.comfyui_url_list:
                task_list.append(self.get_backend_work_status(task))

            resp = await asyncio.gather(*task_list, return_exceptions=True)

            backend_dict = {}
            for i, backend_url in zip(resp, config.comfyui_url_list):
                if isinstance(i, Exception):
                    logger.warning(f"后端 {backend_url} 掉线")

                else:
                    backend_dict[backend_url] = i

            fastest_backend = min(
                backend_dict.items(),
                key=lambda x: len(x[1]["queue_running"]) + len(x[1]["queue_pending"]),
                default=(None, None)
            )

            fastest_backend_url, fastest_backend_info = fastest_backend

            if fastest_backend_url:
                logger.info(f"选择的最快后端: {fastest_backend_url}，队列信息: {fastest_backend_info}")
            else:
                logger.info("没有可用的后端")

            self.backend_url = fastest_backend_url

        else:
            logger.info("未设置多后端功能, 跳过选择")

        return

    def __str__(self):

        format_value = [
            "nb_event", "args", "bot", "prompt", "negative_prompt", "accept_ratio",
            "seed", "steps", "cfg_scale", "denoise_strength", "height", "width",
            "video", "work_flows", "sampler", "scheduler", "batch_size", "model",
            "override", "override_ng", "backend", "batch_count"
        ]

        selected = {key: value for key, value in self.__dict__.items() if key in format_value}
        return str(selected)

    async def save_media(self, media_bytes: list[bytes]):

        path = Path("data/comfyui/output").resolve()

        async def get_hash(img_bytes):
            hash_ = hashlib.md5(img_bytes).hexdigest()
            return hash_

        now = datetime.now()
        short_time_format = now.strftime("%Y-%m-%d")

        user_id_path = self.user_id
        path_ = path / self.media_type / short_time_format / user_id_path
        path_.mkdir(parents=True, exist_ok=True)

        for file_bytes in media_bytes:

            hash_ = await get_hash(file_bytes)
            file = str((path_ / hash_).resolve())

            async with aiofiles.open(str(file) + self.file_format, "wb") as f:
                await f.write(file_bytes)

            async with aiofiles.open(str(file) + ".txt", "w", encoding="utf-8") as f:
                await f.write(self.__str__())

            logger.info(f"文件已保存，路径: {file}")
