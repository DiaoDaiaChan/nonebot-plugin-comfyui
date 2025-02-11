import copy
import json
import random
import time
import traceback
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
from nonebot import logger, Bot
from nonebot.adapters import Event
from typing import Union, Optional
from argparse import Namespace
from pathlib import Path
from datetime import datetime
from aiohttp import TCPConnector
from itertools import islice, zip_longest

from ..config import config
from ..handler import UniMessage
from .utils import pic_audit_standalone, run_later, send_msg_and_revoke
from ..exceptions import ComfyuiExceptions

MAX_SEED = 2 ** 31

OTHER_ACTION = {
    "override", "note", "presets", "media",
    "command", "reg_args", "visible", "output_prefix",
    "daylimit", "lora"
}

__OVERRIDE_SUPPORT_KEYS__ = {
    'keep',
    'value',
    'append_prompt',
    'append_negative_prompt',
    "replace_prompt",
    "replace_negative_prompt",
    'remove',
    "randint",
    "get_text",
    "upscale",
    'image'
}

MODIFY_ACTION = {"output"}


class RespMsg:

    task_id = '1'
    backend_url = ''
    backend_index = 0

    error_msg = ''
    resp_text: str = ''

    resp_img = ''
    resp_video: list = []
    resp_audio: list = []
    media_url = {}


class ComfyuiTaskQueue:

    all_task_id: set = {}
    all_task_dict: dict = {}
    user_task: dict = {}

    def __init__(
            self,
            bot: Bot = None,
            event: Event = None,
            backend: str = None,
            task_id: str = None,
            **kwargs
    ):

        self.bot = bot
        self.event = event
        self.user_id = event.get_user_id()
        self.task_id = task_id

        self.selected_backend = backend
        if backend is not None and backend.isdigit():
            self.backend_url = config.comfyui_url_list[int(backend)]
        else:
            self.backend_url = backend

        self.backend_url: str = self.backend_url if backend else config.comfyui_url

        self.backend = backend

    @classmethod
    async def get_user_task(cls, user_id):
        task_id = cls.user_task.get(user_id, None)
        task_status_dict = await cls.get_task(task_id)

        return task_status_dict

    @classmethod
    async def set_user_task(cls, user_id, task_id):
        cls.user_task.update({user_id: task_id})

    @classmethod
    async def get_history_task(cls, backend_url) -> set:

        api_url = f"{backend_url}/history"

        resp = await ComfyUI.http_request("GET", api_url)
        cls.all_task_set = set(resp.keys())
        cls.all_task_dict = resp

        history_id_set = set(islice(resp.keys(), 20))

        return history_id_set

    @classmethod
    async def get_task(cls, task_id: str | None = None) -> dict:

        task_status_dict = cls.all_task_dict.get(task_id, {})

        return task_status_dict


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


class ComfyUI:
    work_flows_init: list = get_and_filter_work_flows()
    # {backend_url: task_id}
    current_task: dict = {}

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
            work_flows: str = None,
            sampler: Optional[str] = None,
            scheduler: Optional[str] = None,
            batch_size: Optional[int] = None,
            model: Optional[str] = None,
            override: Optional[bool] = False,
            override_ng: Optional[bool] = False,
            backend: Optional[str] = None,
            batch_count: Optional[int] = None,
            forward: Optional[bool] = False,
            concurrency: bool = False,
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
        self.seed: int = seed or random.randint(0, MAX_SEED)
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
        self.forward: bool = forward

        self.comfyui_api_json = None
        self.reflex_json = None
        self.override_backend_setting_dict: dict = {}

        self.selected_backend = backend
        self.backend_url: str = ""

        if backend is not None and backend.isdigit():
            self.backend_url = config.comfyui_url_list[int(backend)]
            self.selected_backend = self.backend_url
        elif backend is not None and not backend.isdigit():
            self.backend_url = backend
            self.selected_backend = self.backend_url
        else:
            self.backend_url = config.comfyui_url

        self.backend_index: int = 0
        self.backend_task: dict = {}
        self.concurrency = concurrency  # 并发生图

        # 用户相关
        self.client_id = uuid.uuid4().hex
        self.user_id = self.nb_event.get_user_id()
        self.task_id = None
        self.adapters = nonebot.get_adapters()
        self.spend_time: int = 0

        self.init_images = []
        self.unimessage = UniMessage.text('')

        self.text: str = ""  # 储存错误信息
        self.text_msg: list[str] = []  #
        self.input_image = False  # 是否需要输入图片

        self.resp_msg: RespMsg = RespMsg()
        self.resp_msg_list: list[RespMsg] = []

    async def send_forward_msg(self) -> bool:

        try:

            if 'OneBot V11' in self.adapters:

                from nonebot.adapters.onebot.v11 import MessageEvent, PrivateMessageEvent, GroupMessageEvent, Message

                async def send_ob11_forward_msg(
                        bot: Bot,
                        event: MessageEvent,
                        name: str,
                        uin: str,
                        msgs: list,
                ) -> dict:

                    def to_json(msg: Message):
                        return {
                            "type": "node",
                            "data":
                                {
                                    "name": name,
                                    "uin": uin,
                                    "content": msg
                                }
                        }

                    messages = [to_json(msg) for msg in msgs]
                    if isinstance(event, GroupMessageEvent):
                        return await bot.call_api(
                            "send_group_forward_msg", group_id=event.group_id, messages=messages
                        )
                    elif isinstance(event, PrivateMessageEvent):
                        return await bot.call_api(
                            "send_private_forward_msg", user_id=event.user_id, messages=messages
                        )

                msg = []

                msg.append(self.unimessage)

                for img, txt in zip_longest(self.uni_image, self.text_msg, fillvalue=""):
                    msg.append(txt + img)

                for video in self.uni_video:
                    msg.append(video)

                # for text in self.uni_long_text:
                #     msg.append(text)

                task_list = []
                for unimsg in msg:
                    task_list.append(unimsg.export())

                msg = await asyncio.gather(*task_list, return_exceptions=False)

                await send_ob11_forward_msg(
                    self.bot,
                    self.nb_event,
                    self.nb_event.sender.nickname,
                    self.nb_event.get_user_id(),
                    msg
                )

                return True
            else:
                return False
        except:
            return False

    async def send_all_msg(self):

        async def normal_msg_send():

            for resp in self.resp_msg_list:
                self.unimessage += (f"任务id: {resp.task_id}, 后端索引: {resp.backend_index}" + resp.error_msg + resp.resp_img + resp.resp_text)

            await self.unimessage.send(reply_to=True)

            # if video_list:
            #     for video in video_list:
            #         for video_ in video:
            #             await video_.send()
        #
        # video_list = []
        # audio_list = []
        #
        # # for resp in self.resp_msg_list:
        # video_list.append(resp.resp_video.split())
        # audio_list.append(resp.resp_audio.split())

        if self.forward:

            is_forward = await self.send_forward_msg()

            if is_forward is False:
                await normal_msg_send()

        else:
            try:
                await normal_msg_send()
            except:
                await self.send_forward_msg()

        # if audio_list:
        #     for audio in audio_list:
        #         for audio_ in audio:
        #             await audio_.send()

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
            self.input_image = True if self.reflex_json.get("load_image", None) else False

    def extract_ratio(self):
        """
        提取宽高比为分辨率
        """
        if ":" in self.accept_ratio:
            try:
                width_ratio, height_ratio = map(int, self.accept_ratio.split(':'))
            except ValueError:
                raise ComfyuiExceptions.ArgsError
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

    async def get_media(self, task_id, backend_url):

        global output_error_msg
        build_error_msg = ''

        resp_msg = RespMsg()

        resp_msg.backend_url = backend_url
        resp_msg.task_id = task_id
        resp_msg.backend_index = config.comfyui_url_list.index(backend_url)

        images_url = []
        video_url = []
        audio_url = []

        media_url = {}

        # if self.interrupt:
        #     raise ComfyuiExceptions.InterruptError

        response: dict = await self.http_request(
            method="GET",
            target_url=f"{backend_url}/history/{task_id}",
        )

        if response == {}:
            build_error_msg += f"任务{task_id}出错: \n" + "返回值为空, 任务可能被清空"
            return

        status_ = response[task_id]["status"]
        messages = status_["messages"]

        if response[task_id]["status"]['status_str'] == 'error':
            error_type = messages[2][0]
            if 'execution_error' in error_type:
                error_msg = messages[2][1]

                output_error_msg = '任务出错!\n'

                error_node = error_msg['node_type']
                output_error_msg += f"出错节点: {error_node}\n"

                exception_msg = error_msg['exception_message']
                output_error_msg += f"错误信息: {exception_msg}\n"

                exception_type = error_msg['exception_type']
                output_error_msg += f"抛出: {exception_type}\n"

                trace_back = error_msg['traceback']
                logger.error(f"任务{task_id}出错: 错误堆栈: {trace_back}\n")

            elif 'execution_interrupted' in error_type:
                output_error_msg = '任务被手动中断!\n'

            build_error_msg += f"\n任务出错:{output_error_msg}"

            # 不抛出异常终止执行 raise ComfyuiExceptions.TaskError(output_error_msg)
        else:

            start_timestamp = messages[0][1]['timestamp']
            end_timestamp = messages[-1][1]['timestamp']

            spend_time = int((end_timestamp - start_timestamp) / 1000)
            self.spend_time += spend_time

            try:

                output_node = self.reflex_json.get('output')

                if isinstance(output_node, (int, str)):
                    output_node = {self.reflex_json.get('media', "image"): [str(output_node)]}

                for key, value in output_node.items():
                    if key == "image":
                        for node in value:
                            images = response[task_id]['outputs'][str(node)]['images']
                            for img in images:
                                filename = img['filename']
                                _, file_format = os.path.splitext(filename)

                                if img['subfolder'] == "":
                                    url = f"{backend_url}/view?filename={filename}"
                                else:
                                    url = f"{backend_url}/view?filename={filename}&subfolder={img['subfolder']}"

                                if img['type'] == "temp":
                                    url = f"{backend_url}/view?filename={filename}&subfolder=&type=temp"

                                images_url.append({"url": url, "file_format": file_format})

                        media_url['image'] = images_url

                    elif key == "video":
                        for node in value:
                            for img in response[task_id]['outputs'][str(node)]['gifs']:
                                filename = img['filename']
                                _, file_format = os.path.splitext(filename)

                                if img['subfolder'] == "":
                                    url = f"{backend_url}/view?filename={filename}"
                                else:
                                    url = f"{backend_url}/view?filename={filename}&subfolder={img['subfolder']}"

                                if img['type'] == "temp":
                                    url = f"{backend_url}/view?filename={filename}&subfolder=&type=temp"

                                video_url.append({"url": url, "file_format": file_format})

                        media_url['video'] = video_url

                    elif key == "audio":
                        for node in value:
                            for img in response[task_id]['outputs'][str(node)]['audio']:
                                filename = img['filename']
                                _, file_format = os.path.splitext(filename)

                                if img['subfolder'] == "":
                                    url = f"{backend_url}/view?filename={filename}"
                                else:
                                    url = f"{backend_url}/view?filename={filename}&subfolder={img['subfolder']}"

                                if img['type'] == "temp":
                                    url = f"{backend_url}/view?filename={filename}&subfolder=&type=temp"

                                audio_url.append({"url": url, "file_format": file_format})

                        media_url['audio'] = audio_url

                    elif key == "text":
                        for node in value:
                            for text in response[task_id]['outputs'][str(node)]['text']:
                                resp_msg.resp_text += text

            except Exception as e:
                if isinstance(e, KeyError):
                    raise ComfyuiExceptions.ReflexJsonOutputError

                else:
                    raise ComfyuiExceptions.GetResultError

        resp_msg.media_url = media_url
        resp_msg.error_msg = build_error_msg
        return resp_msg

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
                "text": self.prompt,
                "Text": self.prompt
            },
            "negative_prompt": {
                "text": self.negative_prompt,
                "Text": self.negative_prompt
            },
            "checkpoint": {
                "ckpt_name": self.model if self.model else None,
                "unet_name": self.model if self.model else None,
                "model": self.model if self.model else None
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

                if isinstance(org_node_id, dict) and item not in MODIFY_ACTION:
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

                                elif override_action == "replace_prompt" and self.override is False:
                                    prompt = raw_api_json[node]['inputs'][key]
                                    if "{prompt}" in prompt:
                                        api_json[node]['inputs'][key] = prompt.replace("{prompt}", self.prompt)

                                elif override_action == "replace_negative_prompt" and self.override_ng is False:
                                    prompt = raw_api_json[node]['inputs'][key]
                                    if "{prompt}" in prompt:
                                        api_json[node]['inputs'][key] = prompt.replace("{prompt}", self.negative_prompt)

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
                if item == "reg_args":
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

    async def heart_beat(self, backend_task: dict):

        async def track_single_task(backend_url: str, task_id: str):
            logger.info(f"{task_id} 开始请求")
            progress_bar = None

            try:
                async with aiohttp.ClientSession() as session:
                    ws_url = f'{backend_url}/ws?clientId={self.client_id}'
                    async with session.ws_connect(ws_url) as ws:
                        self.current_task[backend_url] = task_id
                        logger.debug(f"WS连接成功: {ws_url}")

                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                ws_msg = json.loads(msg.data)

                                if ws_msg['type'] == 'progress':
                                    value = ws_msg['data']['value']
                                    max_value = ws_msg['data']['max']

                                    if not progress_bar:
                                        progress_bar = await asyncio.to_thread(
                                            tqdm, total=max_value,
                                            desc=f"[{backend_url}] Prompt ID: {ws_msg['data']['prompt_id']}",
                                            unit="steps"
                                        )

                                    delta = value - progress_bar.n
                                    await asyncio.to_thread(progress_bar.update, delta)

                                elif ws_msg['type'] == 'executing' and not ws_msg['data']['node']:
                                    logger.info(f"{task_id} 执行完成完成!")
                                    self.resp_msg_list += [await self.get_media(task_id, backend_url)]
                                    await ws.close()

                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                logger.error(f"{task_id} 发生错误: {msg.data}")
                                await ws.close()
                                break
            finally:
                if progress_bar:
                    await asyncio.to_thread(progress_bar.close)
                self.current_task.pop(backend_url, None)

        tasks = []
        for backend_url, tasks_id in backend_task.items():
            for task_id in tasks_id:
                tasks.append(asyncio.create_task(
                    track_single_task(backend_url, task_id)
                ))

        await asyncio.gather(*tasks, return_exceptions=True)


    async def exec_generate(self):

        if self.backend_url is None:
            raise ComfyuiExceptions.NoAvailableBackendError

        if self.concurrency is False:

            await self.select_backend()
            self.unimessage = f"后端索引: {self.backend_index}\n" + self.unimessage

            for i in range(self.batch_count):

                self.seed += 1
                await self.posting()
                await self.heart_beat({self.backend_url: [self.task_id]})

        else:
            backend_taskid = {}
            for i in range(self.batch_count):

                self.seed += 1
                backend_url = await self.select_backend()
                task_id = await self.posting()

                if backend_taskid.get(backend_url, []):
                    old_task_list = backend_taskid[backend_url]
                    old_task_list.append(task_id)
                    backend_taskid[backend_url] = old_task_list

                backend_taskid[backend_url] = [task_id]

            await self.heart_beat(backend_taskid)

        await self.download_img()

    async def posting(self):

        try:
            await self.get_workflows_json()
        except FileNotFoundError:
            raise ComfyuiExceptions.ReflexJsonNotFoundError

        if self.reflex_json.get('override', None):
            self.override_backend_setting_dict = self.reflex_json['override']
            await self.override_backend_setting_func()

        upload_img_resp_list = []

        if self.input_image and not self.init_images:
            raise ComfyuiExceptions.InputFileNotFoundError

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
            raise ComfyuiExceptions.APIJsonError(
                f"请求Comfyui API的时候出现错误: {respond['error']}\n节点错误信息: {respond['node_errors']}"
            )

        task_id = respond['prompt_id']
        self.task_id = task_id

        await ComfyuiTaskQueue(backend=self.backend_url, event=self.nb_event).set_user_task(self.user_id, self.task_id)

        self.backend_index = config.comfyui_url_list.index(self.backend_url)

        queue_ = self.backend_task.get(self.backend_url, None)
        if queue_:
            remain_task = queue_['exec_info']['queue_remaining']
        else:
            remain_task = "N/A"

        await send_msg_and_revoke(
            f"已选择工作流: {self.work_flows}, "
            f"正在生成, 此后端现在共有{remain_task}个任务在执行, "
            f"请稍等. 任务id: {self.task_id}, 后端索引: {self.backend_index}",
            reply_to=True
        )

        return task_id


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
            proxy=False,
            text=False,
    ) -> dict| bytes | str:

        global_ssl_context = ssl.create_default_context()
        global_ssl_context.set_ciphers('DEFAULT')
        global_ssl_context.options |= ssl.OP_NO_SSLv2
        global_ssl_context.options |= ssl.OP_NO_SSLv3
        global_ssl_context.options |= ssl.OP_NO_TLSv1
        global_ssl_context.options |= ssl.OP_NO_TLSv1_1
        global_ssl_context.options |= ssl.OP_NO_COMPRESSION

        connector = TCPConnector(ssl=global_ssl_context)

        async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            try:
                async with session.request(
                        method,
                        target_url,
                        headers=headers,
                        params=params,
                        data=content,
                        ssl=verify,
                ) as response:
                    if text:
                        return await response.text()
                    if format:
                        return await response.json()
                    else:
                        return await response.read()
            except Exception as e:
                raise ComfyuiExceptions.ComfyuiBackendConnectionError(f"请求后端时出现错误: {e}")

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
        try:

            image_byte_save = []
            image_byte_audit = []
            image_byte_tid = {}

            for resp_data in self.resp_msg_list:

                for key, value in resp_data.media_url.items():

                    if key == "text":
                        pass
                    else:
                        for media in value:
                            url = media["url"]

                            response = await self.http_request(
                                method="GET",
                                target_url=url,
                                format=False
                            )

                            logger.info(f"文件: {url}下载成功")

                            if resp_data.task_id in image_byte_tid:
                                image_byte_tid[resp_data.task_id].append({key: (response, media["file_format"])})
                            else:
                                image_byte_tid[resp_data.task_id] = [{key: (response, media["file_format"])}]

                            image_byte_save.append(
                                {
                                    key: (response, media["file_format"])
                                }

                            )

            if config.comfyui_save_image:
                await run_later(self.save_media(image_byte_save), 2)

        except Exception as e:
            raise ComfyuiExceptions.GetResultError(f"获取返回结果时出错: {e}")
        else:
            try:
                await self.audit_func(image_byte_tid)
            except Exception as e:
                raise ComfyuiExceptions.AuditError(f"审核出错: {e}")

    @staticmethod
    def list_to_str(tags_list):
        tags: str = "".join([i+" " for i in tags_list if isinstance(i, str)])
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

        from nonebot.exception import ActionFailed

        try:
            if 'OneBot V11' in self.adapters:
                from nonebot.adapters.onebot.v11.exception import ActionFailed
                from nonebot.adapters.onebot.v11 import MessageSegment

                await self.bot.send_private_msg(user_id=self.user_id, message=MessageSegment.image(image))
            else:
                raise NotImplementedError("暂不支持其他机器人")

        except (NotImplementedError, ActionFailed, Exception) as e:
            if isinstance(e, NotImplementedError):
                logger.warning("发送失败, 暂不支持其他机器人")
            elif isinstance(e, ActionFailed):
                await UniMessage.text('图图私聊发送失败了!是不是没加机器人好友...').send()
            else:
                logger.error(f"发生了未知异常: {e}")
                await UniMessage.text('图图私聊发送失败了!是不是没加机器人好友...').send()

    async def audit_func(self, media_bytes: dict[dict[str, tuple[bytes, str]]]):

        image_list = []
        task_list = []

        if config.comfyui_audit:

            if 'OneBot V11' in self.adapters:
                from nonebot.adapters.onebot.v11 import PrivateMessageEvent

                for resp_ in self.resp_msg_list:
                    for task_id, media_dict in media_bytes.items():
                        if task_id == resp_.task_id:

                            media_list = media_bytes.get(task_id, [])
                            if media_list:
                                for media in media_list:
                                    for file_type, (file_bytes, file_format) in media.items():

                                        if isinstance(self.nb_event, PrivateMessageEvent):
                                            logger.info('私聊, 不进行审核')
                                            if file_type == "image":
                                                resp_.resp_img += UniMessage.image(raw=file_bytes)
                                            elif file_type == "video":
                                                resp_.resp_video.append(UniMessage.video(raw=file_bytes))
                                            elif file_type == "audio":
                                                resp_.resp_audio.append(UniMessage.audio(raw=file_bytes))

                                        else:
                                            if file_type == "image":
                                                image_list.append(file_bytes)
                                                task_list.append(pic_audit_standalone(file_bytes, return_bool=True))
                                            elif file_type == "video":
                                                resp_.resp_video.append(UniMessage.video(raw=file_bytes))
                                            elif file_type == "audio":
                                                resp_.resp_audio.append(UniMessage.audio(raw=file_bytes))

            else:
                for media, resp_ in zip(media_bytes, self.resp_msg_list):
                    for file_type, (file_bytes, file_format) in media.items():

                        if file_type == "image":
                            resp_.resp_img += UniMessage.image(raw=file_bytes)
                        elif file_type == "video":
                            resp_.resp_video.append(UniMessage.video(raw=file_bytes))
                        elif file_type == "audio":
                            resp_.resp_audio.append(UniMessage.audio(raw=file_bytes))

            if task_list:
                resp = await asyncio.gather(*task_list, return_exceptions=False)

                for i, img, resp_ in zip(resp, image_list, self.resp_msg_list):
                    if i:
                        resp_.resp_img += "\n这张图太涩了,私聊发给你了哦!"
                        await run_later(self.send_nsfw_image_to_private(img))
                    else:
                        resp_.resp_img += UniMessage.image(raw=img)

        else:
            for media, resp_ in zip(media_bytes, self.resp_msg_list):
                for file_type, (file_bytes, file_format) in media.items():

                    if file_type == "image":
                        resp_.resp_img += UniMessage.image(raw=file_bytes)
                    elif file_type == "video":
                        resp_.resp_video.append(UniMessage.video(raw=file_bytes))
                    elif file_type == "audio":
                        resp_.resp_audio.append(UniMessage.audio(raw=file_bytes))

    async def get_backend_work_status(self, url):

        resp = await self.http_request("GET", target_url=f"{url}/prompt", timeout=config.comfyui_timeout)
        return resp

    async def select_backend(self):

        backend_dict = {}

        if self.selected_backend:
            resp = await self.get_backend_work_status(self.selected_backend)
            self.backend_task.update({self.selected_backend: resp})
            return

        task_list = []
        for task in config.comfyui_url_list:
            task_list.append(self.get_backend_work_status(task))

        resp = await asyncio.gather(*task_list, return_exceptions=True)

        for i, backend_url in zip(resp, config.comfyui_url_list):
            if isinstance(i, Exception):
                logger.warning(f"后端 {backend_url} 掉线")

            else:
                backend_dict[backend_url] = i

        fastest_backend = min(
            backend_dict.items(),
            key=lambda x: x[1]['exec_info']['queue_remaining'],
            default=(None, None)
        )

        fastest_backend_url, fastest_backend_info = fastest_backend

        if fastest_backend_url:
            logger.info(f"选择的最快后端: {fastest_backend_url}，队列信息: {fastest_backend_info}")
        else:
            logger.info("没有可用的后端")

        self.backend_url = fastest_backend_url
        self.backend_task.update({self.backend_url: fastest_backend_info})

        return fastest_backend_url

    def __str__(self):

        format_value = [
            "nb_event", "args", "bot", "prompt", "negative_prompt", "accept_ratio",
            "seed", "steps", "cfg_scale", "denoise_strength", "height", "width",
            "video", "work_flows", "sampler", "scheduler", "batch_size", "model",
            "override", "override_ng", "backend", "batch_count"
        ]

        selected = {key: value for key, value in self.__dict__.items() if key in format_value}
        return str(selected)

    async def save_media(self, media_bytes: list[dict[str, tuple[bytes, str]]]):

        path = Path("data/comfyui/output").resolve()

        async def get_hash(img_bytes):
            hash_ = hashlib.md5(img_bytes).hexdigest()
            return hash_

        now = datetime.now()
        short_time_format = now.strftime("%Y-%m-%d")

        user_id_path = self.user_id

        for media in media_bytes:

            for file_type, (file_bytes, file_format) in media.items():

                path_ = path / file_type / short_time_format / user_id_path
                path_.mkdir(parents=True, exist_ok=True)

                hash_ = await get_hash(file_bytes)
                file = str((path_ / hash_).resolve())

                async with aiofiles.open(str(file) + file_format, "wb") as f:
                    await f.write(file_bytes)

                async with aiofiles.open(str(file) + ".txt", "w", encoding="utf-8") as f:
                    await f.write(self.__str__())

                logger.info(f"文件已保存，路径: {file}")
