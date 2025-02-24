import aiofiles
import jinja2
import json
import os

from ..config import config, PLUGIN_DIR
from .pw import get_workflow_sc

from nonebot_plugin_alconna import UniMessage


class ComfyuiHelp:

    def __init__(self):
        self.comfyui_workflows_dir = config.comfyui_workflows_dir
        self.workflows_reflex: list[dict] = []
        self.workflows_name: list[str] = []

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

    @staticmethod
    async def get_reg_args(wf):
        if wf is None:
            return "无"
        else:
            args_table = "<table class='sub-table'><thead><tr><th>参数名</th><th>类型</th><th>默认值</th><th>描述</th></tr></thead><tbody>"
            for key, value in wf.items():
                for arg in value['args']:
                    args_table += f"<tr><td>{arg['name_or_flags'][0]}</td><td>{arg['type']}</td><td>{arg['default']}</td><td>{arg['help']}</td></tr>"
            args_table += "</tbody></table>"
            return args_table

    @staticmethod
    async def get_reg_preset_table(wf):
        if wf is None:
            return "无"
        else:
            preset_table = "<table class='sub-table'><thead><tr><th>参数</th><th>预设键</th><th>预设值</th></tr></thead><tbody>"
            for key, value in wf.items():
                for arg in value['args']:
                    if 'preset' in arg:
                        for preset_key, preset_value in arg['preset'].items():
                            # 遍历 name_or_flags 列表
                            name_or_flags = ", ".join(arg.get('name_or_flags', []))
                            preset_table += f"<tr><td>{name_or_flags}</td><td>{preset_key}</td><td>{preset_value}</td></tr>"
            preset_table += "</tbody></table>"
            # 检查表格是否为空
            if preset_table == "<table class='sub-table'><thead><tr><th>参数</th><th>预设键</th><th>预设值</th></tr></thead><tbody></tbody></table>":
                return '无'
            else:
                return preset_table

    async def get_html(self, search):

        len_, content, wf_name = await self.get_reflex_json(search)
        self.workflows_reflex = content
        self.workflows_name = wf_name

        with open(PLUGIN_DIR / 'template' / 'show_wf_template.html', 'r', encoding='utf-8') as f:
            template_str = f.read()

        tbody_rows = []
        for index, (wf, name) in enumerate(zip(self.workflows_reflex, self.workflows_name), 1):

            is_loaded_image = wf.get('load_image', None)
            load_image = wf.get('load_image', {})
            image_count = len(load_image) if isinstance(load_image, dict) else 1

            note = wf.get('note', '').strip()
            override = wf.get('override', {})
            override_msg = '<br>'.join([f'{k}: {v}' for k, v in override.items()])

            media_type = wf.get('media', "image").capitalize()
            reg_command = wf.get('command', '')

            reg_args = wf.get('reg_args')
            reg_args_table = await self.get_reg_args(reg_args)

            reg_preset_str = wf.get('reg_args')
            reg_preset_table = await self.get_reg_preset_table(reg_preset_str)

            available_str = wf.get('available', [])
            available = ''
            if available_str:
                for be in available_str:
                    available += str(be) + ','

                available += '号后端可用'

            with open(PLUGIN_DIR / 'template' / 'row_template.html', 'r', encoding='utf-8') as f:
                row_template = f.read()

            template = jinja2.Template(row_template)
            row = template.render(
                index=index,
                media_type=media_type,
                name=name,
                is_loaded_image=is_loaded_image,
                image_count=image_count,
                override_msg=override_msg,
                reg_command=reg_command,
                reg_args_table=reg_args_table,
                reg_preset_table=reg_preset_table,
                note=note,
                available=available
            )
            tbody_rows.append(row)

            if len_ == 1 and wf.get('visible', True):
                env = jinja2.Environment()
                template = env.from_string(template_str)
                full_html = template.render(tbody_content='\n'.join(tbody_rows))
                sc_image = await get_workflow_sc(name)
                return full_html, UniMessage.image(raw=sc_image)

        env = jinja2.Environment()
        template = env.from_string(template_str)
        full_html = template.render(tbody_content='\n'.join(tbody_rows))

        return full_html, ''