import sys
import subprocess

from .config import Config, config
from nonebot.plugin import require, PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_alconna")
require("nonebot_plugin_htmlrender")

from .command import *
from nonebot import logger


def load_wd_audit():
    try:
        import pandas as pd
        import numpy as np
        import huggingface_hub
        import onnxruntime
    except ModuleNotFoundError:
        logger.info("正在安装本地审核需要的依赖和模型")
        subprocess.run([sys.executable, "-m", "pip", "install", "pandas~=2.2.3", "numpy~=2.2.3", "pillow~=11.0.0", "huggingface_hub==0.28.1"])
        subprocess.run([sys.executable, "-m", "pip", "install", "onnxruntime~=1.20.1"])

    logger.info("正在本地审核加载实例")
    from .backend.wd_audit import WaifuDiffusionInterrogator

    wd_instance = WaifuDiffusionInterrogator(**config.comfyui_wd_model)

    wd_instance.load()
    logger.info("WD模型加载成功")
    return wd_instance


def load_nude_audit():
    try:
        from nudenet import NudeDetector
        nudenet_detector_instance = NudeDetector(model_path=config.comfyui_nude_model_path,
                                                 inference_resolution=640)
    except ModuleNotFoundError:
        logger.info("正在安装本地审核需要的依赖")
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "nudenet>=3.4.2"])
        nudenet_detector_instance = NudeDetector(model_path=config.comfyui_nude_model_path,
                                                 inference_resolution=640)

    logger.info("NudeNet模型加载成功")

    return nudenet_detector_instance


if config.comfyui_audit_local:
    if config.comfyui_audit_model == 1:
        wd_instance = load_wd_audit()

    if config.comfyui_audit_model == 2:
        nudenet_detector_instance = load_nude_audit()

    # if config.comfyui_audit_model == 3:
    #     convnextv_instance = load_cv_audit()

    if config.comfyui_dual_audit:
        wd_instance = load_wd_audit()
        nudenet_detector_instance = load_nude_audit()


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
