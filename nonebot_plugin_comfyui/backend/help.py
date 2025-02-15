import aiofiles
import json
import os

from ..config import config
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
        resp_text = ''
        if wf is None:
            return None
        else:
            for key, value in wf.items():
                for arg in value['args']:
                    resp_text += f"注册的参数: {arg['name_or_flags'][0]}, 类型: {arg['type']}, 默认值: {arg['default']}, 描述: {arg['help']}<br>"

            return resp_text

    async def get_html(self, search) -> (str, UniMessage):

        len_, content, wf_name = await self.get_reflex_json(search)
        self.workflows_reflex = content
        self.workflows_name = wf_name

        html_template = """
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>ComfyUI 工作流列表</title>
            <style>
                * {{ box-sizing: border-box; }}
                body {{ 
                    font-family: 'Segoe UI', system-ui, sans-serif;
                    line-height: 1.6;
                    margin: 0;
                    padding: 20px;
                    background: #f8f9fa;
                }}
                .table-wrapper {{
                    max-width: 100%;
                    overflow-x: auto;
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    min-width: 500px;
                }}
                th, td {{
                    padding: 12px 15px;
                    border-bottom: 1px solid #e9ecef;
                    text-align: left;
                }}
                th {{
                    background: #2c3e50;
                    color: white;
                    font-weight: 600;
                    position: sticky;
                    top: 0;
                }}
                tr:nth-child(even) {{
                    background-color: #f8f9fa;
                }}
                tr:hover {{
                    background-color: #f1f3f5;
                    transition: background 0.2s;
                }}
                .media-type {{
                    font-weight: 500;
                    color: #2c3e50;
                }}
                .image-count {{
                    color: #e67e22;
                    font-weight: bold;
                }}
                h1 {{
                    color: #2c3e50;
                    margin-bottom: 1.5rem;
                }}
                h2 {{
                    color: #34495e;
                    margin: 1rem 0;
                    font-size: 1.25rem;
                }}
            </style>
        </head>
        <body>
            <h1>🖼️ ComfyUI 工作流</h1>
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>输出类型</th>
                            <th>工作流名称</th>
                            <th>需图片输入</th>
                            <th>图片数量</th>
                            <th>覆写设置</th>
                            <th>注册命令</th>
                            <th>注册参数</th>
                            <th>备注说明</th>
                        </tr>
                    </thead>
                    <tbody>
                        {tbody_content}
                    </tbody>
                </table>
            </div>
        </body>
        </html>
                """
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
            reg_args = await self.get_reg_args(wf.get('reg_args'))

            row = f"""
                <tr>
                    <td>{index}</td>
                    <td><span class="media-type">{media_type}</span></td>
                    <td><strong>{name}</strong></td>
                    <td>{"✅ 是" if is_loaded_image else "❌ 否"}</td>
                    <td><span class="image-count">{image_count}张</span></td>
                    <td>{override_msg or '-'}</td>
                    <td>{reg_command or '-'}</td>
                    <td>{reg_args or '无'}</td>
                    <td>{note or '-'}</td>
                </tr>
            """
            tbody_rows.append(row)

            if len_ == 1 and wf.get('visible', True):
                sc_image = await get_workflow_sc(name)
                return html_template.format(tbody_content='\n'.join(tbody_rows)), UniMessage.image(raw=sc_image)

        full_html = html_template.format(tbody_content='\n'.join(tbody_rows))
        return full_html, UniMessage.text('')

