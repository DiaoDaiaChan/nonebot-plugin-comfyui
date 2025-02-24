import sys
import subprocess

from .config import Config, config
from nonebot.plugin import require, PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_alconna")
require("nonebot_plugin_htmlrender")

from .command import *

if config.comfyui_audit_local:
    from nonebot import logger
    try:
        import pandas as pd
        import numpy as np
        import huggingface_hub
        import onnxruntime
    except ModuleNotFoundError:
        logger.info("正在安装本地审核需要的依赖和模型")
        subprocess.run([sys.executable, "-m", "pip", "install", "pandas", "numpy", "pillow", "huggingface_hub"])
        subprocess.run([sys.executable, "-m", "pip", "install", "onnxruntime"])

    logger.info("正在本地审核加载实例")
    from .backend.wd_audit import WaifuDiffusionInterrogator

    wd_instance = WaifuDiffusionInterrogator(
        name='WaifuDiffusion',
        repo_id="SmilingWolf/wd-vit-tagger-v3",
        revision='v2.0',
        model_path='model.onnx',
        tags_path='selected_tags.csv'
    )

    wd_instance.load()
    logger.info("模型加载成功")


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
