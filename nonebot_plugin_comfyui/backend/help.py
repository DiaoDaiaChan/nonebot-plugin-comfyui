# from .comfyui import ComfyuiUI
import aiofiles
import json
import os

from ..config import config
from .pw import get_workflow_sc
from typing import Union, Any

from nonebot_plugin_alconna import UniMessage


class ComfyuiHelp:

    def __init__(self):
        self.comfyui_workflows_dir = config.comfyui_workflows_dir
        self.workflows_reflex: list[dict] = []
        self.workflows_name: list[str] = []

    @staticmethod
    async def get_reg_args(wf):
        resp_text = ''
        if wf is None:
            return None
        else:
            for key, value in wf.items():
                for arg in value['args']:
                    resp_text += f"注册的参数: {arg['name_or_flags'][0]}, 类型: {arg['type']}, 默认值: {arg['default']}, 描述: {arg['help']}<br>"

            return resp_text

    @staticmethod
    async def get_reflex_json(search=None) -> (int, list, list):

        workflows_reflex = []
        workflows_name = []

        if isinstance(search, str):
            if search.isdigit():
                search = int(search)
            search = search
        else:
            search = None
        for filename in os.listdir(config.comfyui_workflows_dir):
            if filename.endswith('_reflex.json'):
                file_path = os.path.join(config.comfyui_workflows_dir, filename)
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    workflows_reflex.append(json.loads(content))
                    workflows_name.append(filename.replace('_reflex.json', ''))

        if isinstance(search, int):
            if 0 <= search < len(workflows_name):
                return 1, [workflows_reflex[search-1]], [workflows_name[search-1]]
            else:
                raise IndexError(f"Index {search} out of range. Available indices: 0-{len(workflows_name) - 1}")

        if isinstance(search, str):
            matched_reflex = []
            matched_names = []
            for name, content in zip(workflows_name, workflows_reflex):
                if search in name:
                    matched_reflex.append(content)
                    matched_names.append(name)
            return len(matched_names), matched_reflex, matched_names

        return len(workflows_name), workflows_reflex, workflows_name

    async def get_md(self, search) -> (str, UniMessage):

        len_, content, wf_name = await self.get_reflex_json(search)
        self.workflows_reflex = content
        self.workflows_name = wf_name

        head = '''
# ComfyUI 工作流
## 工作流列表
|编号|输出类型|    工作流名称     | 是否需要输入图片 | 输入图片数量 |   覆写的设置值    |注册的命令|注册的参数|备注|
|:-:|:-:|:---------------:|:--------------:|:--------------:|:--------------:|:-:|:-:|:--:|
'''
        build_form = head + ''
        index = 0

        for wf, name in zip(self.workflows_reflex, self.workflows_name):

            index += 1

            is_loaded_image = wf.get('load_image', None)
            load_image = wf.get('load_image', None)
            image_count = len(load_image.keys()) if isinstance(load_image, dict) else 1

            note = wf.get('note', '')
            override = wf.get('override', None)

            override_msg = ''

            if override:
                for key, value in override.items():
                    override_msg += f'{key}: {value}<br>'

            media_type = wf.get('media', "image")
            reg_command = wf.get('command', None)

            reg_args = await self.get_reg_args(wf.get('reg_args', None))

            build_form += f'|{index}|{media_type}|  {name}   |  {"是" if is_loaded_image else "否"}  |{image_count}张|  {override_msg}   |{reg_command if reg_command else ""}|{reg_args}|{note}|\n'

            if len_ == 1:

                sc_image = await get_workflow_sc(name)
                return build_form, UniMessage.image(raw=sc_image)

        return build_form, UniMessage.text('')

