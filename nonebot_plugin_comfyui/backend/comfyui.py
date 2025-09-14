import copy
import json
import random
import traceback
import uuid
import os
import re

import aiofiles
import aiohttp
import asyncio
import hashlib

import nonebot

from tqdm import tqdm
from nonebot import logger, Bot
from nonebot.adapters import Event
from typing import Union, Optional
from argparse import Namespace
from pathlib import Path
from datetime import datetime
from itertools import islice

from ..config import config, BACKEND_URL_LIST
from nonebot_plugin_alconna import UniMessage
from .utils import (
    pic_audit_standalone,
    run_later,
    send_msg_and_revoke,
    get_and_filter_work_flows,
    http_request,
    translate_api,
    txt_audit,
    get_qr,
    get_ava_backends,
    weighted_choice,
    get_all_loras
)
from ..exceptions import ComfyuiExceptions

MAX_SEED = 2 ** 31

OTHER_ACTION = {
    "override", "note", "presets", "media",
    "command", "reg_args", "visible", "output_prefix",
    "daylimit", "lora", "available", "reflex", "only_available"
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

MODIFY_ACTION = {"output", "reg_args"}

reflex_dict = {
    'sampler': {
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
    },
    'scheduler': {
        "Automatic": "normal",
        "Karras": "karras",
        "Exponential": "exponential",
        "SGM Uniform": "sgm_uniform",
        "Simple": "simple",
        "Normal": "normal",
        "DDIM": "ddim_uniform",
        "Beta": "beta"
    }
}


class DefaultValue:
    width: int = 832
    height: int = 1216
    accept_ratio: str = None
    shape: str = None
    steps: int = 28
    cfg_scale: float = 7.0
    denoise_strength: float = 1.0
    sampler: str = "dpmpp_2m"
    scheduler: str = "karras"
    batch_size: int = 1
    batch_count: int = 1
    model = ""
    override: bool = False
    override_ng: bool = False
    forward: bool = False
    concurrency: bool = False
    pure: bool = False
    notice: bool = False

    preset_prompt: str = ''
    preset_negative_prompt: str = ''

    @staticmethod
    def set_default_value(params_dict):
        for key, value in params_dict.items():
            if hasattr(DefaultValue, key):
                setattr(DefaultValue, key, value)

    def __init__(self):
        if config.comfyui_random_params_enable:
            for k, v in config.comfyui_random_params.items():
                if hasattr(self, k):
                    set_value = weighted_choice(v)
                    setattr(self, k, set_value)

    def override_value(self):
        if config.comfyui_random_params_enable:
            for k, v in config.comfyui_random_params.items():
                if hasattr(self, k):
                    set_value = weighted_choice(v)
                    setattr(self, k, set_value)

    def get_default_value_instance(self):
        if config.comfyui_random_params_enable:
            return self
        else:
            return DefaultValue


DefaultValue.set_default_value(config.comfyui_default_value)


class RespMsg:

    def __init__(self, task_id: str = "", backend_url: str = ""):
        self.task_id = task_id
        self.backend_url: str = backend_url
        self.backend_index: int = BACKEND_URL_LIST.index(backend_url) if backend_url in BACKEND_URL_LIST else -1

        self.error_msg: str = ''
        self.resp_text: str = ''

        self.resp_img = ''
        self.resp_video: list = []
        self.resp_audio: list = []
        self.media_url: dict = {}

        self.image_byte = []


class ComfyuiHistory:
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
            self.backend_url = BACKEND_URL_LIST[int(backend)]
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

        resp = await http_request("GET", api_url)
        cls.all_task_set = set(resp.keys())
        cls.all_task_dict = resp

        history_id_set = set(islice(resp.keys(), 20))

        return history_id_set

    @classmethod
    async def get_task(cls, task_id: str | None = None) -> dict:

        task_status_dict = cls.all_task_dict.get(task_id, {})

        return task_status_dict


class ComfyuiTaskQueue:
    all_task_id = set()
    all_task_dict = {}
    user_task = {}

    @classmethod
    async def get_user_task(cls, user_id: str):
        user_tasks = cls.user_task.get(user_id, {})
        if not user_tasks:
            return {}

        return user_tasks

    @classmethod
    async def set_user_task(
            cls,
            user_id: str,
            task_id: str,
            backend_index: int,
            work_flow: str,
            status: str = "pending"
    ) -> None:

        if user_id not in cls.user_task:
            cls.user_task[user_id] = {}

        cls.user_task[user_id][task_id] = {
            "backend_index": backend_index,
            "work_flow": work_flow,
            "status": status,
        }

        cls.all_task_id.add(task_id)

    @classmethod
    async def get_task(cls, task_id: Optional[str] = None):

        if task_id is None:
            return {}

        task_status_dict = cls.all_task_dict.get(task_id, {})
        return task_status_dict

    @classmethod
    async def update_task_status(cls, task_id: str, status: str) -> None:

        if task_id in cls.all_task_dict:
            cls.all_task_dict[task_id]["status"] = status

        # 更新用户任务中的状态
        for user_tasks in cls.user_task.values():
            if task_id in user_tasks:
                user_tasks[task_id]["status"] = status


class ComfyUIQueue:
    def __init__(self, queue_size=10):
        self.queue = asyncio.Queue(maxsize=queue_size)
        self.semaphore = asyncio.Semaphore(queue_size)


class ComfyUI:
    work_flows_init: list = get_and_filter_work_flows()
    current_task: dict = {}

    @classmethod
    def update_wf(cls, search=None, index=None):
        cls.work_flows_init = get_and_filter_work_flows(search, index=index)
        return cls.work_flows_init

    def __init__(
            self,
            nb_event: Event,
            bot: nonebot.Bot,
            args: Optional[Namespace] = None,
            prompt=None,
            negative_prompt=None,
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
            concurrency: Optional[bool] = False,
            shape: Optional[str] = None,
            silent: Optional[bool] = False,
            notice: Optional[bool] = False,
            no_trans: Optional[bool] = False,
            pure: Optional[bool] = False,
            send_msg_private: Optional[bool] = True,
            **kwargs
    ):
        default_value = DefaultValue().get_default_value_instance()

        # 映射参数相关
        if prompt is None:
            prompt = [""]
        if negative_prompt is None:
            negative_prompt = [""]
        self.reflex_dict = reflex_dict

        self.work_flows = work_flows

        if self.work_flows == config.comfyui_default_workflows:
            if config.comfyui_random_wf:
                self.work_flows = random.choice(config.comfyui_random_wf_list)
        else:
            if work_flows:
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
        self.override = override or default_value.override
        self.override_ng = override_ng or default_value.override_ng

        self.prompt: str = (
            [default_value.preset_prompt] + prompt
            if default_value.preset_prompt and not self.override
            else prompt
        )
        self.negative_prompt: str = (
            [default_value.preset_negative_prompt] + negative_prompt
            if default_value.preset_negative_prompt and not self.override_ng
            else negative_prompt
        )

        self.accept_ratio: str = accept_ratio or default_value.shape
        if self.accept_ratio is None:
            self.height: int = height or default_value.height
            self.width: int = width or default_value.width
        else:
            self.width, self.height = self.extract_ratio()
        self.shape: str = shape or default_value.shape

        self.seed: int = seed or random.randint(0, MAX_SEED)
        self.steps: int = steps or default_value.steps
        self.cfg_scale: float = cfg_scale or default_value.cfg_scale
        self.denoise_strength: float = denoise_strength or default_value.denoise_strength

        self.sampler: str = (
            self.reflex_dict['sampler'].get(sampler, "dpmpp_2m") if
            sampler not in self.reflex_dict['sampler'].values() else
            sampler or default_value.sampler
        )
        self.scheduler: str = (
            self.reflex_dict['scheduler'].get(scheduler, "normal") if
            scheduler not in self.reflex_dict['scheduler'].values() else
            scheduler or default_value.scheduler
        )

        self.batch_size: int = batch_size or default_value.batch_size
        self.batch_count: int = batch_count or default_value.batch_count
        self.total_count: int = self.batch_count * self.batch_size
        self.model: str = model or config.comfyui_model or default_value.model
        self.forward: bool = forward or default_value.forward
        self.loras: list = []

        self.preset_prompt = default_value.preset_prompt
        self.preset_negative_prompt = default_value.preset_negative_prompt

        self.comfyui_api_json = None
        self.reflex_json = None
        self.override_backend_setting_dict: dict = {}

        self.selected_backend = backend
        self.backend_url: str = ""

        if backend is not None and backend.isdigit():
            self.backend_url = BACKEND_URL_LIST[int(backend)]
            self.selected_backend = self.backend_url
        elif backend is not None and not backend.isdigit():
            self.backend_url = backend
            self.selected_backend = self.backend_url
        else:
            self.backend_url = config.comfyui_url

        self.backend_index: int = 0
        self.backend_task: dict = {}
        self.available_backends: set[int] = set({})
        self.concurrency = concurrency or default_value.concurrency
        self.silent = silent or config.comfyui_silent
        self.notice = notice or default_value.notice
        self.no_trans = no_trans
        self.pure = pure or default_value.pure
        self.send_msg_private = send_msg_private

        # 用户相关
        self.client_id = None
        self.user_id = self.nb_event.get_user_id()
        self.task_id = None
        self.adapters = nonebot.get_adapters()
        self.spend_time: int = 0

        self.init_images = []
        self.unimessage = UniMessage.text('')
        self.uni_long_text: list = []
        self.input_image = False  # 是否需要输入图片

        self.resp_msg: RespMsg = RespMsg()
        self.resp_msg_list: list[RespMsg] = []

    def set_max_values(self, max_dict):
        for key, max_value in max_dict.items():
            if hasattr(self, key):
                current_value = getattr(self, key)
                if current_value is not None and current_value > max_value:
                    setattr(self, key, max_value)

    async def send_forward_msg(self, msg) -> bool:

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

                task_list = []
                for unimsg in msg:
                    task_list.append(unimsg.export())

                if self.uni_long_text:
                    for uni in self.uni_long_text:
                        task_list.append(UniMessage.text(uni))

                msg = await asyncio.gather(*task_list, return_exceptions=True)

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

    async def normal_msg_send(self):

        for resp in self.resp_msg_list:

            for video in resp.resp_video:
                await run_later(video.send())

        await self.unimessage.send(reply_to=True)

    async def send_extra_info(self, message, reply=False):
        if not self.silent:
            await send_msg_and_revoke(message, reply)

    async def send_all_msg(self):

        audit_mode = ''
        if config.comfyui_audit is False:
            audit_mode = '关闭'
        elif config.comfyui_audit_level == 1:
            audit_mode = '宽松'
        elif config.comfyui_audit_level == 2:
            audit_mode = '严格'
        elif config.comfyui_audit_level == 3:
            audit_mode = '非常严格'
        elif config.comfyui_audit_level == 100:
            audit_mode = '全部拦截'

        msg_list = []

        for resp in self.resp_msg_list:
            if self.pure:
                msg_ = resp.error_msg + resp.resp_img + resp.resp_text
            else:
                msg_ = f"任务id: {resp.task_id}\n审核模式: {audit_mode}\n后端索引: {resp.backend_index}\n" + resp.error_msg + resp.resp_img + resp.resp_text
            self.unimessage += msg_
            msg_list.append(msg_)

        if self.forward:

            is_forward = await self.send_forward_msg(msg_list)

            if is_forward is False:
                await self.normal_msg_send()

        else:
            try:
                await self.normal_msg_send()
            except:
                await self.send_forward_msg(msg_list)

        for resp_ in self.resp_msg_list:
            for audio in resp_.resp_audio:
                await audio.send()
            for video in resp_.resp_video:
                await video.send()

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
            return 832, 1216

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

        output_error_msg = ''
        build_error_msg = ''

        resp_msg = RespMsg(task_id, backend_url)

        images_url = []
        video_url = []
        audio_url = []

        media_url = {}

        response: dict = await http_request(
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
                "Text": self.prompt,
                "prompt": self.prompt
            },
            "negative_prompt": {
                "text": self.negative_prompt,
                "Text": self.negative_prompt,
                "prompt": self.negative_prompt
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
                        inputs_dict = update_dict.get('inputs', {})
                        for key, value in update_mapping[item].items():
                            if key in inputs_dict:
                                inputs_dict[key] = value

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
                                inputs_dict = update_dict.get('inputs', {})
                                for key, value in update_mapping[item].items():
                                    if key in inputs_dict:
                                        inputs_dict[key] = value

            else:
                if item == "reg_args":
                    reg_args = node_id
                    for node, item_ in reg_args.items():
                        for arg in item_["args"]:

                            args_dict = vars(self.args)
                            org_key = arg["dest"]
                            type_ = None
                            args_key = None
                            preset_dict = {}

                            if "preset" in arg:
                                type_ = arg["type"]
                                preset_dict = arg["preset"]

                            if "dest_to_value" in arg:
                                json_key = arg["dest_to_value"][arg["dest"]]
                                args_key = list(arg["dest_to_value"].keys())[0]

                            else:
                                json_key = arg['dest']

                            update_node = {}

                            if "default" in arg:
                                default_value = arg["default"]
                                update_node[json_key] = default_value

                            if hasattr(self.args, org_key):
                                get_value = args_key if args_key else json_key

                                update_value = args_dict[get_value]

                                if preset_dict:
                                    if update_value in preset_dict:
                                        update_value = preset_dict[update_value]

                                if type_ == "int":
                                    update_value = int(update_value)
                                elif type_ == "float":
                                    update_value = float(update_value)
                                elif type_ == "bool":
                                    update_value = bool(update_value)

                                update_node[json_key] = update_value

                            api_json[node]['inputs'].update(update_node)

                elif item == "reflex":
                    reflex_list = node_id
                    for backend_index, node_reflex in reflex_list.items():
                        if self.backend_index == int(backend_index):
                            for node, item_ in node_reflex.items():
                                for k, v in item_.items():
                                    api_json[node]['inputs'][k] = v

                elif item == "lora" and self.loras:

                    lora_template = {
                        "inputs": {
                            "lora_name": "diaodiao-000005.safetensors",
                            "strength_model": 1,
                            "strength_clip": 1,
                            "model": [
                                "4",
                                0
                            ],
                            "clip": [
                                "4",
                                1
                            ]
                        },
                        "class_type": "LoraLoader",
                        "_meta": {
                            "title": "Load LoRA"
                        }
                    }
                    build_lora_node = {}

                    if isinstance(node_id, list):
                        lora_node = node_id
                        for node in lora_node:

                            for k, v in node.items():

                                if len(self.loras) == 1:
                                    tmp_lora_template = copy.deepcopy(lora_template)
                                    self_node_id = k
                                    from_model_node_id = v['from']['model']
                                    from_clip_node_id = v['from']['clip']

                                    lora_name, lora_weight = self.loras[0]

                                    tmp_lora_template['inputs']['model'][0] = str(from_model_node_id)
                                    tmp_lora_template['inputs']['clip'][0] = str(from_clip_node_id)

                                    tmp_lora_template['inputs']['strength_model'] = lora_weight
                                    tmp_lora_template['inputs']['strength_clip'] = lora_weight
                                    tmp_lora_template['inputs']['lora_name'] = lora_name

                                    for k, v in v['to'].items():
                                        if k == "model":
                                            for node_ in v:
                                                api_json[str(node_)]['inputs'][k][0] = str(self_node_id)
                                        elif k == "clip":
                                            for node_ in v:
                                                api_json[str(node_)]['inputs'][k][0] = str(self_node_id)

                                    build_lora_node[str(self_node_id)] = tmp_lora_template
                                else:
                                    self_node_id = int(k) - 1
                                    from_model_node_id = str(v['from']['model'])
                                    from_clip_node_id = str(v['from']['clip'])

                                    for index, (lora_name, lora_weight) in enumerate(self.loras):
                                        tmp_lora_template = copy.deepcopy(lora_template)
                                        self_node_id += 1

                                        if index == 0:
                                            final_model_node_id = from_model_node_id
                                            final_clip_node_id = from_clip_node_id

                                        elif index != len(self.loras) - 1:
                                            final_model_node_id = str(self_node_id - 1)
                                            final_clip_node_id = str(self_node_id - 1)

                                        else:
                                            final_model_node_id = str(self_node_id - 1)
                                            final_clip_node_id = str(self_node_id - 1)

                                            for k, v in v['to'].items():
                                                if k == "model":
                                                    for node_ in v:
                                                        api_json[str(node_)]['inputs'][k][0] = str(self_node_id)
                                                elif k == "clip":
                                                    for node_ in v:
                                                        api_json[str(node_)]['inputs'][k][0] = str(self_node_id)

                                        tmp_lora_template['inputs']['model'][0] = final_model_node_id
                                        tmp_lora_template['inputs']['clip'][0] = final_clip_node_id

                                        tmp_lora_template['inputs']['strength_model'] = lora_weight
                                        tmp_lora_template['inputs']['strength_clip'] = lora_weight
                                        tmp_lora_template['inputs']['lora_name'] = lora_name
                                        tmp_lora_template['_meta']['title'] = "nonebot_plugin_comfyui auto load"

                                        build_lora_node[str(self_node_id)] = tmp_lora_template

                    else:

                        if len(self.loras) != 1:
                            link_model_list = []
                            link_clip_list = []

                            for apijson_node_id, node_data in api_json.items():
                                match_model_node = node_data['inputs'].get('model')
                                match_clip_node = node_data['inputs'].get('clip')
                                if match_model_node:
                                    if match_model_node[0] == str(node_id):
                                        link_model_list.append(apijson_node_id)
                                if match_clip_node:
                                    if match_clip_node[0] == str(node_id):
                                        link_clip_list.append(apijson_node_id)

                        enum_node = node_id - 1
                        for index, (lora_name, lora_weight) in enumerate(self.loras):
                            tmp_lora_template = copy.deepcopy(lora_template)
                            enum_node += 1

                            if index == 0:
                                raw_lora_data = api_json[str(node_id)]

                                raw_lora_data['inputs']['strength_model'] = lora_weight
                                raw_lora_data['inputs']['strength_clip'] = lora_weight
                                raw_lora_data['inputs']['lora_name'] = lora_name

                                build_lora_node[str(node_id)] = raw_lora_data

                            elif index != len(self.loras) - 1:
                                final_model_node_id = str(enum_node - 1)
                                final_clip_node_id = str(enum_node - 1)

                                tmp_lora_template['inputs']['model'][0] = final_model_node_id
                                tmp_lora_template['inputs']['clip'][0] = final_clip_node_id

                                tmp_lora_template['inputs']['strength_model'] = lora_weight
                                tmp_lora_template['inputs']['strength_clip'] = lora_weight
                                tmp_lora_template['inputs']['lora_name'] = lora_name
                                tmp_lora_template['_meta']['title'] = "nonebot_plugin_comfyui auto load"
                                build_lora_node[str(enum_node)] = tmp_lora_template

                            else:
                                final_model_node_id = str(enum_node - 1)
                                final_clip_node_id = str(enum_node - 1)

                                for model_ in link_model_list:
                                    api_json[str(model_)]['inputs']['model'][0] = str(enum_node)
                                for clip_ in link_clip_list:
                                    api_json[str(clip_)]['inputs']['clip'][0] = str(enum_node)

                                tmp_lora_template['inputs']['model'][0] = final_model_node_id
                                tmp_lora_template['inputs']['clip'][0] = final_clip_node_id

                                tmp_lora_template['inputs']['strength_model'] = lora_weight
                                tmp_lora_template['inputs']['strength_clip'] = lora_weight
                                tmp_lora_template['inputs']['lora_name'] = lora_name
                                tmp_lora_template['_meta']['title'] = "nonebot_plugin_comfyui auto load"
                                build_lora_node[str(enum_node)] = tmp_lora_template

                    api_json.update(build_lora_node)

        logger.debug(api_json)
        await run_later(self.compare_dicts(api_json, self.comfyui_api_json), 0.5)
        return api_json

    async def track_single_task(self, backend_url: str, task_id: str, client_id: str):
        logger.info(f"任务: {task_id} 开始跟踪 At {client_id} client ID")
        progress_bar = None

        try:
            async with aiohttp.ClientSession() as session:
                ws_url = f'{backend_url}/ws?clientId={client_id}'
                async with session.ws_connect(ws_url) as ws:
                    self.current_task[backend_url] = task_id
                    logger.debug(f"WS连接成功: {ws_url}")

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            ws_msg = json.loads(msg.data)

                            if ws_msg['type'] == 'progress' and task_id == ws_msg['data']['prompt_id']:
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

                            elif ws_msg['type'] == 'executing' and ws_msg['data']['node'] is None:
                                logger.info(f"{task_id} 执行完成完成!")
                                await ComfyuiTaskQueue.update_task_status(task_id, 'finish')
                                if self.notice:
                                    await run_later(
                                        self.send_msg_to_private(
                                            f"你的任务已经完成, 获取结果发送 queue -get {task_id} -be {self.backend_index}",
                                            is_image=False
                                        )
                                    )
                                # 获取返回的文件url
                                self.resp_msg_list += [await self.get_media(task_id, backend_url)]
                                await ws.close()
                                return

                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logger.error(f"{task_id} 发生错误: {msg.data}")
                            await ws.close()
                            break
        finally:
            if progress_bar:
                await asyncio.to_thread(progress_bar.close)
            self.current_task.pop(backend_url, None)

    async def heart_beat(self, backend_task: list):

        tasks = []
        for backend_url, task_id, client_id in backend_task:
            tasks.append(asyncio.create_task(
                self.track_single_task(backend_url, task_id, client_id)
            ))

        await asyncio.gather(*tasks, return_exceptions=True)

    async def prompt_init(self, tags_list) -> str:
        tags: str = " ".join(str(i) for i in tags_list if isinstance(i, str))
        tags = re.sub(r"\[CQ[^\s]*?]", "", tags)
        tags = tags.replace("\\\\", "\\")

        if config.comfyui_translate and not self.no_trans:
            tags_list_split = [tag.strip() for tag in tags.split(",") if tag.strip()]  # 使用split分割标签
            tagzh = [tag for tag in tags_list_split if re.search('[\u4e00-\u9fa5]', tag)]
            tags_en = ""
            if tagzh:
                tagzh_str = ",".join(tagzh)
                if config.comfyui_ai_prompt:
                    from ..amusement.llm_tagger import get_user_session
                    logger.info("使用AI翻译")
                    to_openai = f"{tagzh_str}+prompts"
                    try:
                        tags_en = await get_user_session(20020204).main(to_openai)
                        logger.info(f"ai生成prompt: {tags_en}")
                    except Exception as e:
                        logger.error(f"AI翻译失败: {e}, 回退到普通翻译")
                        tags_en = await translate_api(tagzh_str, "en")
                else:
                    tags_en = await translate_api(tagzh_str, "en")
            tags_other = [tag for tag in tags_list_split if not re.search('[\u4e00-\u9fa5]', tag)]
            all_tags = ", ".join(filter(None, [tags_en, ", ".join(tags_other)]))
            tags = all_tags
        return tags

    async def get_lora_from_prompt(self):

        loras = []
        clean_parts = []

        for part in self.prompt.split(','):
            part = part.strip()
            if part.startswith('<lora:') and part.endswith('>'):
                content = part[6:-1]
                style, value = content.split(':', 1)
                loras.append((style.strip(), float(value.strip())))
            else:
                clean_parts.append(part)

        self.prompt = ', '.join(clean_parts)
        return loras

    async def get_apply_loras(self):

        if not config.comfyui_auto_lora:
            return

        loras = await self.get_lora_from_prompt()

        if not loras:
            return
        else:
            all_loras = await get_all_loras(self.backend_url)

            for lora_name, lora_weight in loras:
                for lora in all_loras:
                    if lora_name in lora:
                        logger.info(f"找到lora: {lora}")
                        self.loras.append((lora, lora_weight))
                        break

    async def exec_generate(self, daily_call=None):

        # 获取工作流json
        try:
            await self.get_workflows_json()
            # 工作流每日调用限制
            if daily_call:
                limit_ = self.reflex_json.get('daylimit')
                if limit_:
                    if limit_ < daily_call:
                        raise ComfyuiExceptions.ReachWorkFlowExecLimitations

        except FileNotFoundError:
            raise ComfyuiExceptions.ReflexJsonNotFoundError

        self.set_max_values(config.comfyui_max_dict)
        # prompt初始化
        task_list = [self.prompt_init(self.prompt), self.prompt_init(self.negative_prompt)]
        self.prompt, self.negative_prompt = await asyncio.gather(*task_list, return_exceptions=False)
        # 文字审核
        resp = await txt_audit(str(self.prompt) + str(self.negative_prompt))
        if "yes" in resp:
            raise ComfyuiExceptions.TextContentNotSafeError

        if self.backend_url is None:
            raise ComfyuiExceptions.NoAvailableBackendError

        # 是否是并发生成
        if self.concurrency:

            task_info_list = []
            for i in range(self.batch_count):
                self.seed += 1
                # 选择后端
                await self.select_backend()
                # 开始请求任务
                task_info = await self.posting()
                task_info_list.append(task_info)
            # 监听任务
            await self.heart_beat(task_info_list)

        else:

            await self.select_backend()
            for i in range(self.batch_count):
                self.seed += 1
                task_info = await self.posting()
                await self.heart_beat([task_info])

        self.resp_msg_list = [item for item in self.resp_msg_list if item is not None]
        # 下载任务
        await self.download_img()

    async def posting(self):

        await self.get_apply_loras()

        # 获取reflex json
        if self.reflex_json.get('override', None):
            self.override_backend_setting_dict = self.reflex_json['override']
            # 覆写设置
            await self.override_backend_setting_func()

        # 设置分辨率
        shape_preset_dict = config.comfyui_shape_preset
        if self.shape:
            if self.shape in shape_preset_dict:
                shape_tuple = shape_preset_dict.get(self.shape)
                self.width = shape_tuple[0]
                self.height = shape_tuple[1]
            else:
                if 'x' in self.shape:
                    self.width, self.height = map(int, self.shape.split('x'))

        upload_img_resp_list = []

        # 检查是否需要图片
        if self.input_image and not self.init_images:
            raise ComfyuiExceptions.InputFileNotFoundError

        # 上传图片
        if self.init_images:
            for image in self.init_images:
                resp = await self.upload_image(image, uuid.uuid4().hex)
                upload_img_resp_list.append(resp)

        # 更新API JSON
        api_json = await self.update_api_json(upload_img_resp_list)

        self.client_id = uuid.uuid4().hex
        input_ = {
            "client_id": self.client_id,
            "prompt": api_json
        }

        # 开始请求
        respond = await http_request(
            method="POST",
            target_url=f"{self.backend_url}/prompt",
            content=json.dumps(input_, indent=2)
        )

        if respond.get("error", None):
            logger.error(respond)
            raise ComfyuiExceptions.APIJsonError(
                f"请求Comfyui API的时候出现错误: {respond['error']}\n节点错误信息: {respond['node_errors']}"
            )

        task_id = respond['prompt_id']
        self.task_id = task_id

        await ComfyuiTaskQueue.set_user_task(self.user_id, task_id, self.backend_index, self.work_flows)

        queue_ = self.backend_task.get(self.backend_url, None)
        if queue_:
            remain_task = queue_['exec_info']['queue_remaining']
        else:
            remain_task = "N/A"

        await self.send_extra_info(
            f"已选择工作流: {self.work_flows}, "
            f"正在生成, 此后端现在共有{remain_task}个任务在执行, "
            f"请稍等. 任务id: {self.task_id}, 后端索引: {self.backend_index}",
            reply=True
        )

        return self.backend_url, task_id, self.client_id

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
            image_byte_tid = {}

            for resp_data in self.resp_msg_list:
                if resp_data:
                    for key, value in resp_data.media_url.items():

                        if key != "text":
                            for media in value:
                                url = media["url"]

                                response = await http_request(
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
    async def compare_dicts(dict1, dict2):
        modified_keys = {k for k in dict1.keys() & dict2.keys() if dict1[k] != dict2[k]}

        if not modified_keys:
            logger.info("节点映射情况: (无变化)")
            return

        build_info = "节点映射情况:\n"
        for node_id in sorted(modified_keys):
            build_info += f"节点ID: {node_id}\n"
            new_data = dict1[node_id].get('inputs', {})
            old_data = dict2[node_id].get('inputs', {})

            if new_data != old_data:
                for key in sorted(new_data.keys() | old_data.keys()):
                    new_value = new_data.get(key)
                    old_value = old_data.get(key)

                    if new_value != old_value:
                        build_info += f"{key}:\n"
                        build_info += f"值变动: {new_value} -> {old_value}\n"
                        build_info += "\n"
            else:
                build_info += "(仅节点ID发生变化，inputs 无变化)\n"

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

    async def send_msg_to_private(self, msg, is_image=True):

        if self.send_msg_private is False:
            return

        from nonebot.exception import ActionFailed

        try:
            if 'OneBot V11' in self.adapters:
                from nonebot.adapters.onebot.v11.exception import ActionFailed
                from nonebot.adapters.onebot.v11 import MessageSegment

                await self.bot.send_private_msg(user_id=self.user_id,
                                                message=MessageSegment.image(msg) if is_image else msg)
            else:
                raise NotImplementedError("暂不支持其他机器人")

        except (NotImplementedError, ActionFailed, Exception) as e:
            traceback.print_exc()
            if isinstance(e, NotImplementedError):
                logger.warning("发送失败, 暂不支持其他机器人")
            elif isinstance(e, ActionFailed):
                await UniMessage.text('私聊发送失败了!是不是没加机器人好友...').send()
            else:
                logger.error(f"发生了未知异常: {e}")
                await UniMessage.text('私聊发送失败了!是不是没加机器人好友...').send()

    async def audit_func(self, media_bytes):

        audit_tasks = []
        other_media = []

        async def audit_image_task(resp_, file_bytes):

            is_nsfw = await pic_audit_standalone(file_bytes, return_bool=True)
            return resp_, is_nsfw, file_bytes

        if config.comfyui_audit:
            if 'OneBot V11' in self.adapters:
                from nonebot.adapters.onebot.v11 import PrivateMessageEvent

                for resp_ in self.resp_msg_list:
                    task_id = resp_.task_id
                    media_list = media_bytes.get(task_id, [])
                    for media in media_list:
                        for file_type, (file_bytes, file_format) in media.items():
                            if isinstance(self.nb_event, PrivateMessageEvent):
                                other_media.append((resp_, file_type, file_bytes))
                            else:
                                if file_type == "image":
                                    task = audit_image_task(resp_, file_bytes)
                                    audit_tasks.append(task)
                                else:
                                    other_media.append((resp_, file_type, file_bytes))

                if audit_tasks:
                    audit_results = await asyncio.gather(*audit_tasks)
                    for resp_, is_nsfw, file_bytes in audit_results:
                        if is_nsfw:
                            if config.comfyui_r18_action == 1:
                                resp_.resp_img += "\n这张图太涩了,私聊发给你了哦!" if self.send_msg_private else "\n这张图太涩了"
                                await self.send_msg_to_private(file_bytes)
                            elif config.comfyui_r18_action == 2:
                                qr_img, _ = await get_qr(file_bytes, self.bot)
                                qr_img = UniMessage.image(raw=qr_img)
                                resp_.resp_img += qr_img
                            elif config.comfyui_r18_action == 3:
                                _, img_url = await get_qr(file_bytes, self.bot)
                                resp_.resp_img += f"\n这张图太涩了, 这是图片url: {img_url}"
                            elif config.comfyui_r18_action == 4:
                                resp_.resp_img += "\n这张图太涩了, 不给你看"

                        else:
                            if config.comfyui_img_send == 1:
                                resp_.resp_img += UniMessage.image(raw=file_bytes)
                            elif config.comfyui_img_send == 2:
                                qr_img, _ = await get_qr(file_bytes, self.bot)
                                qr_img = UniMessage.image(raw=qr_img)
                                resp_.resp_img += qr_img
                            elif config.comfyui_img_send == 3:
                                _, img_url = await get_qr(file_bytes, self.bot)
                                resp_.resp_img += f"\n这是图片url: {img_url}"

                for resp_, file_type, file_bytes in other_media:
                    if file_type == "image":
                        resp_.resp_img += UniMessage.image(raw=file_bytes)
                    elif file_type == "video":
                        resp_.resp_video.append(UniMessage.video(raw=file_bytes))
                    elif file_type == "audio":
                        resp_.resp_audio.append(UniMessage.audio(raw=file_bytes))

        else:
            for resp_ in self.resp_msg_list:
                media_list = media_bytes.get(resp_.task_id, [])
                for media in media_list:
                    for file_type, (file_bytes, file_format) in media.items():
                        if file_type == "image":
                            resp_.resp_img += UniMessage.image(raw=file_bytes)
                        elif file_type == "video":
                            resp_.resp_video.append(UniMessage.video(raw=file_bytes))
                        elif file_type == "audio":
                            resp_.resp_audio.append(UniMessage.audio(raw=file_bytes))

    async def select_backend(self):
        fastest_backend_index = None
        # 手动选择后端
        if self.selected_backend:

            if self.selected_backend not in BACKEND_URL_LIST:
                self.backend_index = -1
                return self.selected_backend

        self.available_backends, backend_dict = await get_ava_backends()

        if self.selected_backend:
            if self.selected_backend in backend_dict:
                self.backend_task.update({self.selected_backend: backend_dict[self.selected_backend]})

        else:

            fastest_backend = min(
                backend_dict.items(),
                key=lambda x: x[1]['exec_info']['queue_remaining'],
                default=(None, None)
            )

            fastest_backend_url, fastest_backend_info = fastest_backend

            if fastest_backend_url:
                logger.info(f"选择的最快后端: {fastest_backend_url}，队列信息: {fastest_backend_info}")
            else:
                logger.error("没有可用的后端")
                raise ComfyuiExceptions.NoAvailableBackendError

            self.backend_url = fastest_backend_url
            fastest_backend_index = BACKEND_URL_LIST.index(fastest_backend_url)
            self.backend_task.update({self.backend_url: fastest_backend_info})

        self.backend_index = BACKEND_URL_LIST.index(self.backend_url)

        available_in = self.reflex_json.get('available', None)
        only_available = self.reflex_json.get('only_available', None)

        if only_available:
            # 完成这里
            pass

        if available_in:
            ava_backend_inter = set(available_in).intersection(self.available_backends)

            if not ava_backend_inter:
                raise ComfyuiExceptions.NoAvailableBackendForSelectedWorkflow
            else:
                if self.backend_index in ava_backend_inter:
                    if fastest_backend_index and fastest_backend_index in ava_backend_inter:
                        self.backend_url = BACKEND_URL_LIST[fastest_backend_index]
                    else:
                        self.backend_url = BACKEND_URL_LIST[random.choice(list(ava_backend_inter))]
                else:
                    if self.backend_index in available_in:
                        await self.send_extra_info(
                            f'警告，所选的后端(索引: {self.backend_index})掉线，无法执行工作流({self.work_flows})，已自动切换',
                            reply=True
                        )

                    else:
                        await self.send_extra_info(
                            f'警告，所选的后端(索引: {self.backend_index})不支持当前工作流({self.work_flows})，已自动切换',
                            reply=True
                        )

                    if fastest_backend_index and fastest_backend_index in ava_backend_inter:
                        self.backend_url = BACKEND_URL_LIST[fastest_backend_index]
                    else:
                        self.backend_url = BACKEND_URL_LIST[random.choice(list(ava_backend_inter))]
        else:
            if self.backend_index not in self.available_backends:

                await self.send_extra_info(
                    f'警告, 所选的后端(索引: {self.backend_index})掉线, 已经自动选择到支持的后端',
                    reply=True
                )

                if fastest_backend_index:
                    self.backend_url = BACKEND_URL_LIST[fastest_backend_index]
                else:
                    self.backend_url = BACKEND_URL_LIST[random.choice(list(self.available_backends))]

        self.backend_index = BACKEND_URL_LIST.index(self.backend_url)

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
