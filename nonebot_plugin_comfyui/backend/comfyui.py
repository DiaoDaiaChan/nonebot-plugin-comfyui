import copy
import json
import random
import uuid
import os
import re

import aiofiles
import aiohttp
import asyncio

from tqdm import tqdm
from nonebot import logger, get_adapters
from nonebot.adapters import Event
from typing import Union, Optional
from argparse import Namespace

from ..config import config
from ..handler import UniMessage
from .utils import pic_audit_standalone

MAX_SEED = 2 ** 32


def get_and_filter_work_flows(search=None) -> list:
    if isinstance(search, str):
        search = search
    else:
        search = None

    wf_files = []
    for root, dirs, files in os.walk(config.comfyui_workflows_dir):
        for file in files:
            if search:
                if file.endswith('.json') and search in file and not file.endswith('_reflex.json'):
                    wf_files.append(file.replace('.json', ''))
            else:
                if file.endswith('.json') and not file.endswith('_reflex.json'):
                    wf_files.append(file.replace('.json', ''))

    return wf_files


class ComfyuiUI:
    work_flows_init: list = get_and_filter_work_flows()

    @classmethod
    def update_wf(cls, search=None):
        cls.work_flows_init = get_and_filter_work_flows(search)
        return cls.work_flows_init

    def __init__(
            self,
            nb_event: Event,
            args: Namespace,
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

        # 必要参数
        self.nb_event = nb_event
        self.args = args

        # 绘图参数相关
        self.prompt: str = self.list_to_str(prompt or "")
        self.negative_prompt: str = self.list_to_str(negative_prompt or "")
        self.accept_ratio: str = accept_ratio
        if self.accept_ratio is None:
            self.height: int = height or 1024
            self.width: int = width or 1024
        else:
            self.width, self.height = self.extract_ratio()
        self.seed: int = seed or random.randint(0, 2 ^ 32)
        self.steps: int = steps or 20
        self.cfg_scale: float = cfg_scale or 7.0
        self.denoise_strength: float = denoise_strength or 1.0
        self.video: bool = video or False

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
        self.model: str = model or config.comfyui_model

        # ComfyuiAPI相关
        if work_flows is None:
            work_flows = config.comfyui_default_workflows
        for wf in self.update_wf():
            if work_flows in wf:
                self.work_flows = wf
                break
            else:
                self.work_flows = "txt2img"

        logger.info(f"选择工作流: {self.work_flows}")
        self.api_json = None
        self.reflex_json = None
        self.override_backend_setting_dict: dict = {}
        self.backend_url: str = config.comfyui_url

        # 用户相关
        self.client_id = uuid.uuid4().hex
        self.user_id = self.nb_event.get_user_id()
        self.task_id = None

        # 流媒体相关
        self.init_images: list[bytes] = []
        self.media_url: list = []
        self.unimessage: UniMessage = UniMessage.text("")
        self.media_type: str = 'image'

    async def get_workflows_json(self):
        async with aiofiles.open(
                f"{config.comfyui_workflows_dir}/{self.work_flows}.json",
                'r',
                encoding='utf-8'
        ) as f:
            self.api_json = json.loads(await f.read())

        async with aiofiles.open(
                f"{config.comfyui_workflows_dir}/{self.work_flows}_reflex.json",
                'r',
                encoding='utf-8'
        ) as f:
            self.reflex_json = json.loads(await f.read())

    def extract_ratio(self, max_res=None):
        """
        提取宽高比为分辨率
        """

        if ":" in self.accept_ratio:
            width_ratio, height_ratio = map(int, self.accept_ratio.split(':'))
        else:
            return 768, 1152

        max_resolution = config.comfyui_base_res
        aspect_ratio = width_ratio / height_ratio
        if aspect_ratio >= 1:
            width = int(min(max_resolution, max_resolution))
            height = int(width / aspect_ratio)
        else:
            height = int(min(max_resolution, max_resolution))
            width = int(height * aspect_ratio)

        return width, height

    def update_api_json(self, init_images):
        api_json = copy.deepcopy(self.api_json)
        raw_api_json = copy.deepcopy(self.api_json)

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
                "ckpt_name": self.model if self.model else None
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

            if node_id and item not in ("override", "note"):

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
                    temp_dict = copy.deepcopy(update_mapping)
                    for node, override_dict in org_node_id.items():
                        single_node_or = override_dict.get("override", {})

                        if single_node_or:
                            for key, override_action in single_node_or.items():

                                if override_action == "randint":
                                    api_json[node]['inputs'][key] = random.randint(0, MAX_SEED)

                                elif override_action == "keep":
                                    org_cons = raw_api_json[node]['inputs'][key]

                                elif override_action == "append_prompt":
                                    prompt = raw_api_json[node]['inputs'][key]
                                    prompt = self.prompt + prompt
                                    api_json[node]['inputs'][key] = prompt

                                elif override_action == "append_negative_prompt":
                                    prompt = raw_api_json[node]['inputs'][key]
                                    prompt = self.negative_prompt + prompt
                                    api_json[node]['inputs'][key] = prompt

                                elif "upscale" in override_action:
                                    scale = 1.5
                                    if "_" in override_action:
                                        scale = override_action.split("_")[1]

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
                #
                # else:
                #     node_id = [node_id] if isinstance(node_id, int) else node_id
                #
                #     for id_ in node_id:
                #         id_ = str(id_)
                #         update_dict = api_json.get(id_, None)
                #         if update_dict and item in update_mapping:
                #             api_json[id_]['inputs'].update(update_mapping[item])

        self.compare_dicts(api_json, self.api_json)
        self.api_json = api_json

    async def heart_beat(self, id_):
        logger.info(f"{id_} 开始请求")

        async def get_images():

            response = await self.http_request(
                method="GET",
                target_url=f"{self.backend_url}/history/{id_}",
            )

            if response:
                try:
                    if self.media_type == 'image':
                        for img in response[id_]['outputs'][str(self.reflex_json.get('output', 9))]['images']:
                            img_url = f"{self.backend_url}/view?filename={img['filename']}"
                            self.media_url.append(img_url)

                    elif self.media_type == 'video':
                        pass

                    elif self.media_type == 'audio':
                        pass
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

        self.update_api_json(upload_img_resp_list)

        input_ = {
            "client_id": self.client_id,
            "prompt": self.api_json
        }

        respone = await self.http_request(
            method="POST",
            target_url=f"{self.backend_url}/prompt",
            content=json.dumps(input_)
        )

        if respone.get("error", None):
            logger.error(respone)
            raise RuntimeError(respone["status_code"])

        self.task_id = respone['prompt_id']

        await self.heart_beat(self.task_id)
        await self.download_img()

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

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
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

    async def upload_image(self, image_data: bytes, name, image_type="input", overwrite=False):

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

        if 'OneBot V11' in get_adapters():
            logger.info('私聊, 不进行审核')
            from nonebot.adapters.onebot.v11 import PrivateMessageEvent
            if isinstance(self.nb_event, PrivateMessageEvent):
                for img in image_byte:
                    self.unimessage += UniMessage.image(raw=img)
            else:
                await self.audit_func(image_byte)
        else:
            await self.audit_func(image_byte)

    @staticmethod
    def list_to_str(tags_list):
        tags: str = "".join([i+" " for i in tags_list if isinstance(i,str)])
        tags = re.sub("\[CQ[^\s]*?]", "", tags)
        tags = tags.split(",")
        return ','.join(tags)

    @staticmethod
    def compare_dicts(dict1, dict2):

        modified_keys = {k for k in dict1.keys() & dict2.keys() if dict1[k] != dict2[k]}
        for key in modified_keys:
            logger.info(f"API请求值映射: {key} -> {dict1[key]} -> {dict2[key]}")

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

    async def audit_func(self, image_byte):
        if config.comfyui_audit:
            task_list = []
            for img in image_byte:
                task_list.append(pic_audit_standalone(img, return_bool=True))

            resp = await asyncio.gather(*task_list, return_exceptions=False)

            for i, img in zip(resp, image_byte):
                if i:
                    self.unimessage += UniMessage.text("\n这张图太涩了")
                else:
                    self.unimessage += UniMessage.image(raw=img)
        else:
            for img in image_byte:
                self.unimessage += UniMessage.image(raw=img)