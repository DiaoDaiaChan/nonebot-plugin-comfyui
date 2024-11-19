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
    async def get_reflex_json(search=None):

        workflows_reflex = []
        workflows_name = []

        if isinstance(search, str):
            search = search
        else:
            search = None

        for filename in os.listdir(config.comfyui_workflows_dir):
            if (search in filename and filename.endswith('_reflex.json')) if search else filename.endswith('_reflex.json'):
                file_path = os.path.join(config.comfyui_workflows_dir, filename)
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    workflows_reflex.append(json.loads(content))
                    workflows_name.append(filename.replace('_reflex.json', ''))

        return len(workflows_name), workflows_reflex, workflows_name

    async def get_md(self, search) -> Union[str, UniMessage]:

        len_, content, wf_name = await self.get_reflex_json(search)
        self.workflows_reflex = content
        self.workflows_name = wf_name

        head = '''
# ComfyUI 工作流
## 工作流列表
|编号|输出类型|    工作流名称     | 是否需要输入图片 | 输入图片数量 |   覆写的设置值    |注册的命令|备注|
|:-:|:-:|:---------------:|:--------------:|:--------------:|:--------------:|:-:|:--:|
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

            build_form += f'|{index}|{media_type}|  {name}   |  {"是" if is_loaded_image else "否"}  |{image_count}张|  {override_msg}   |{reg_command if reg_command else ""}|{note}|\n'

            if len_ == 1:

                sc_image = await get_workflow_sc(name)
                return build_form, UniMessage.image(raw=sc_image)

        return build_form, UniMessage.text('')

