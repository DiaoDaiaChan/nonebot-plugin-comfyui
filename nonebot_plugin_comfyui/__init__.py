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
from nonebot_plugin_htmlrender import md_to_pic
from arclet.alconna import Alconna

from .config import Config, config
from .handler import comfyui_handler
from .backend.comfyui import ComfyuiUI
from .backend.help import ComfyuiHelp

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


async def rebuild_parser(wf, reg_args: dict | None =None):

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

help_ = on_command("comfyui帮助", aliases={"帮助", "菜单", "help"}, priority=5, block=True)

view_workflow = on_alconna(
    Alconna("查看工作流", Args["search?", str]),
    priority=5,
    block=True
)


async def set_command():
    reg_command = []

    _, content, wf_name = await ComfyuiHelp().get_reflex_json()

    for wf, wf_name in zip(content, wf_name):
        if "command" in wf:
            reg_args = None

            print(wf)

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


async def build_help_text(reg_command):

    help_text = f'''
# comfyui 绘图插件

## 发送 prompt

发送 `prompt [正面提示词]` 来进行一次最简单的生图。

## 额外注册的指令
{"<br>".join(reg_command)}

### 其他参数

- `-u` 负面提示词
- `--ar` 画幅比例
- `-s` 种子
- `--steps` 采样步数
- `--cfg` CFG scale
- `-n` 去噪强度
- `-高` 高度
- `-宽` 宽度
- `-v` 视频输出
- `-wf` 工作流
- `-sp` 采样器
- `-sch` 调度器
- `-b` 每批数量
- `-bc` 生成几批
- `-m` 模型
- `-o` 不使用内置正面提示词
- `-on` 不使用内置负面提示词
- `-be` 选择指定的后端索引/url

---

### 其他命令

- 查看工作流 (查看所有工作流)
- 查看工作流 flux (查看带有 flux 的工作流)

---

### 示例
```
prompt a girl, a beautiful girl, masterpiece -u badhand   
-ar 1:1 -s 123456 -steps 20 -cfg 7.5 -n 1   
-height 512 -width 512 -sp "DPM++ 2M Karras"
```

**By:** nonebot-plugin-comfyui  
**github.com/DiaoDaiaChan/nonebot-plugin-comfyui**
'''
    return help_text


@help_.handle()
async def _():
    img = await md_to_pic(md=await build_help_text(reg_command))
    await UniMessage.image(raw=img).finish()


@view_workflow.handle()
async def _(search):

    md_, msg = await ComfyuiHelp().get_md(search)
    img = await md_to_pic(md=md_, width=2000)

    msg = UniMessage.image(raw=img) + msg
    await msg.finish()

reg_command = asyncio.run(set_command())
