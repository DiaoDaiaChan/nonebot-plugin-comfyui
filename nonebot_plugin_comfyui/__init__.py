import asyncio
import os
import json

from nonebot import logger
from nonebot.plugin import PluginMetadata, inherit_supported_adapters
from nonebot.rule import ArgumentParser
from nonebot.plugin.on import on_shell_command, on_command

from nonebot.plugin import require
require("nonebot_plugin_alconna")
require("nonebot_plugin_htmlrender")
from nonebot_plugin_alconna import on_alconna, Args, UniMessage
from nonebot_plugin_htmlrender import html_to_pic, md_to_pic
from arclet.alconna import Alconna

from .config import Config, config
from .handler import comfyui_handler
from .backend.comfyui import ComfyUI
from .backend.help import ComfyuiHelp
from .handler import queue_handler, api_handler
from .backend.update_check import check_package_update

PLUGIN_VERSION = '0.6.0'

comfyui_parser = ArgumentParser()

comfyui_parser.add_argument("prompt", nargs="*", help="标签", type=str)
comfyui_parser.add_argument("-u", "-U", nargs="*", dest="negative_prompt", type=str, help="Negative prompt")
comfyui_parser.add_argument("--ar", "-ar", dest="accept_ratio", type=str, help="Accept ratio")
comfyui_parser.add_argument("--s", "-s", dest="seed", type=int, help="Seed")
comfyui_parser.add_argument("--steps", "-steps", "-t", dest="steps", type=int, help="Steps")
comfyui_parser.add_argument("--cfg", "-cfg", dest="cfg_scale", type=float, help="CFG scale")
comfyui_parser.add_argument("-n", "--n", dest="denoise_strength", type=float, help="Denoise strength")
comfyui_parser.add_argument("-高", "--height", dest="height", type=int, help="Height")
comfyui_parser.add_argument("-宽", "--width", dest="width", type=int, help="Width")
comfyui_parser.add_argument("-v", dest="video", action="store_true", help="Video output flag")
comfyui_parser.add_argument("-o", dest="override", action="store_true", help="不使用预设的正面")
comfyui_parser.add_argument("-on", dest="override_ng", action="store_true", help="不使用预设的负面提示词")
comfyui_parser.add_argument("-wf", "--work-flows", dest="work_flows", type=str, help="Workflows")
comfyui_parser.add_argument("-sp", "--sampler", dest="sampler", type=str, help="采样器")
comfyui_parser.add_argument("-sch", "--scheduler", dest="scheduler", type=str, help="调度器")
comfyui_parser.add_argument("-b", "--batch_size", dest="batch_size", type=int, help="每批数量", default=1)
comfyui_parser.add_argument("-bc", "--batch_count", dest="batch_count", type=int, help="批数", default=1)
comfyui_parser.add_argument("-m", "--model", dest="model", type=str, help="模型")
comfyui_parser.add_argument("-be", "--backend", dest="backend", type=str, help="后端索引或者url")
comfyui_parser.add_argument("-f", dest="forward", action="store_true", help="使用转发消息")
comfyui_parser.add_argument("-gif", dest="gif", action="store_true", help="使用gif图片进行图片输入")
comfyui_parser.add_argument("-con", "-并发", dest="concurrency", action="store_true", help="并发使用多后端生图")

queue_parser = ArgumentParser()

queue_parser.add_argument("--track", "-t", "-追踪", "--track_task", dest="track", action="store_true", help="后端当前的任务")
queue_parser.add_argument("-d", "--delete", dest="delete", type=str, help="从队列中清除指定的任务")
queue_parser.add_argument("-c", "--clear", "-clear", dest="clear", action="store_true", help="清除后端上的所有任务")
queue_parser.add_argument("-stop", "--stop", dest="stop", action="store_true", help="停止当前生成")

queue_parser.add_argument("-be", "--backend", dest="backend", type=str, help="后端索引或者url", default="0")
queue_parser.add_argument("-i", "--id", dest="task_id", type=str, help="需要查询的任务id")
queue_parser.add_argument("-v", "--view", dest="view", action="store_true", help="查看历史任务")

queue_parser.add_argument("-g", "--get", "-get", dest="get_task", type=str, help="需要获取具体信息的任务")
queue_parser.add_argument("-index", "--index", dest="index", type=str, help="需要获取的任务id范围", default="0-10")
# queue_parser.add_argument("-m", "--media", dest="media_type", type=str, help="需要获取具体信息的任务的输出类型", default='image')

api_parser = ArgumentParser()
api_parser.add_argument("-g", "--get", "-get", dest="get", type=str, help="获取所有节点", default="all")
api_parser.add_argument("-be", "--backend", dest="backend", type=str, help="后端索引或者url", default="0")


async def rebuild_parser(wf, reg_args: dict | None = None):

    comfyui_parser = ArgumentParser()

    if reg_args:

        type_mapping = {
            "int": int,
            "str": str,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
        }

        for node_arg in list(reg_args.values()):
            for arg in node_arg['args']:
                if arg["type"] in type_mapping:
                    arg["type"] = type_mapping[arg["type"]]
                    flags = arg["name_or_flags"]

                    del arg["name_or_flags"]
                    if "dest_to_value" in arg:
                        del arg["dest_to_value"]

                    if "preset" in arg:
                        arg["type"] = str
                        del arg["preset"]

                    comfyui_parser.add_argument(*flags, **arg)
                    logger.info(f"成功注册命令参数: {arg['dest']}")

    comfyui_parser.add_argument("prompt", nargs="*", help="标签", type=str)
    comfyui_parser.add_argument("-u", "-U", nargs="*", dest="negative_prompt", type=str, help="Negative prompt")
    comfyui_parser.add_argument("--ar", "-ar", dest="accept_ratio", type=str, help="Accept ratio")
    comfyui_parser.add_argument("--s", "-s", dest="seed", type=int, help="Seed")
    comfyui_parser.add_argument("--steps", "-steps", "-t", dest="steps", type=int, help="Steps")
    comfyui_parser.add_argument("--cfg", "-cfg", dest="cfg_scale", type=float, help="CFG scale")
    comfyui_parser.add_argument("-n", "--n", dest="denoise_strength", type=float, help="Denoise strength")
    comfyui_parser.add_argument("-高", "--height", dest="height", type=int, help="Height")
    comfyui_parser.add_argument("-宽", "--width", dest="width", type=int, help="Width")
    comfyui_parser.add_argument("-v", dest="video", action="store_true", help="Video output flag")
    comfyui_parser.add_argument("-o", dest="override", action="store_true", help="不使用预设的正面")
    comfyui_parser.add_argument("-on", dest="override_ng", action="store_true", help="不使用预设的负面提示词")
    comfyui_parser.add_argument("-wf", "--work-flows", dest="work_flows", type=str, help="Workflows", default=wf)
    comfyui_parser.add_argument("-sp", "--sampler", dest="sampler", type=str, help="采样器")
    comfyui_parser.add_argument("-sch", "--scheduler", dest="scheduler", type=str, help="调度器")
    comfyui_parser.add_argument("-b", "--batch_size", dest="batch_size", type=int, help="每批数量", default=1)
    comfyui_parser.add_argument("-bc", "--batch_count", dest="batch_count", type=int, help="每批数量", default=1)
    comfyui_parser.add_argument("-m", "--model", dest="model", type=str, help="模型")
    comfyui_parser.add_argument("-be", "--backend", dest="backend", type=str, help="后端索引或者url")
    comfyui_parser.add_argument("-f", dest="forward", action="store_true", help="使用转发消息")
    comfyui_parser.add_argument("-gif", dest="gif", action="store_true", help="使用gif图片进行图片输入")
    comfyui_parser.add_argument("-con", "-并发", dest="concurrency", action="store_true", help="并发使用多后端生图")

    return comfyui_parser


__plugin_meta__ = PluginMetadata(
    name="Comfyui绘图插件",
    description="专门适配Comfyui的绘图插件",
    usage="基础生图命令: prompt, 发送 comfyui帮助 来获取支持的参数",
    config=Config,
    type="application",
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
    extra={"author": "DiaoDaiaChan", "email": "437012661@qq.com"},
    homepage="https://github.com/DiaoDaiaChan/nonebot-plugin-comfyui"
)

comfyui = on_shell_command(
    "prompt",
    parser=comfyui_parser,
    priority=5,
    block=True,
    handlers=[comfyui_handler]
)

queue = on_shell_command(
    "queue",
    parser=queue_parser,
    priority=5,
    block=True,
    handlers=[queue_handler]
)

api = on_shell_command(
    "capi",
    parser=api_parser,
    priority=5,
    block=True,
    handlers=[api_handler]
)


help_ = on_command("comfyui帮助", aliases={"帮助", "菜单", "help"}, priority=1, block=False)

view_workflow = on_alconna(
    Alconna("查看工作流", Args["search?", str]),
    priority=5,
    block=True
)


async def start_up_func():

    async def set_command():
        reg_command = []

        _, content, wf_name = await ComfyuiHelp().get_reflex_json()

        for wf, wf_name in zip(content, wf_name):
            if "command" in wf:
                reg_args = None

                if "reg_args" in wf:
                    reg_args = wf["reg_args"]

                comfyui_parser = await rebuild_parser(wf_name, reg_args)
                on_shell_command(
                    wf["command"],
                    parser=comfyui_parser,
                    priority=5,
                    block=True,
                    handlers=[comfyui_handler]
                )

                logger.info(f"成功注册命令: {wf['command']}")
                reg_command.append(wf["command"])

        return reg_command

    return await set_command()


async def build_help_text(reg_command):

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
                </tr>
                </tr>
            </table>
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


@help_.handle()
async def _():
    img = await html_to_pic(html=await build_help_text(reg_command))

    msg = UniMessage.text('项目地址: github.com/DiaoDaiaChan/nonebot-plugin-comfyui')
    img = UniMessage.image(raw=img)
    msg = msg + img

    await msg.finish()


@view_workflow.handle()
async def _(search):

    html_, msg = await ComfyuiHelp().get_html(search)
    img = await html_to_pic(html=html_)

    msg = UniMessage.image(raw=img) + msg
    await msg.finish()

reg_command = asyncio.run(start_up_func())
