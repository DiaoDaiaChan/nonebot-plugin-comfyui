import os
import shutil
import sys
import subprocess

from nonebot import get_plugin_config, logger, get_driver
from pathlib import Path
from pydantic import BaseModel


class Config(BaseModel):
    comfyui_url: str = "http://127.0.0.1:8188"
    comfyui_url_list: list = ["http://127.0.0.1:8188", "http://127.0.0.1:8288"]
    comfyui_multi_backend: bool = False
    comfyui_model: str = ""
    comfyui_workflows_dir: str = "./data/comfyui"
    comfyui_default_workflows: str = "txt2img"
    comfyui_max_res: int = 2048
    comfyui_base_res: int = 1024
    comfyui_audit: bool = True
    comfyui_audit_local: bool = False
    comfyui_audit_site: str = "http://server.20020026.xyz:7865"
    comfyui_save_image: bool = True
    comfyui_cd: int = 20
    comfyui_day_limit: int = 50
    comfyui_limit_as_seconds: bool = False
    comfyui_timeout: int = 5
    comfyui_superusers: list = []


config = get_plugin_config(Config)
wf_dir = Path(config.comfyui_workflows_dir)
superusers = list(get_driver().config.superusers)
config.comfyui_superusers = superusers

if config.comfyui_multi_backend is False:
    config.comfyui_url_list = [config.comfyui_url]

if wf_dir.exists():
    logger.info(f"Comfyui工作流文件夹存在")
else:
    wf_dir.resolve().mkdir(parents=True, exist_ok=True)

    current_dir = Path(os.path.dirname(os.path.abspath(__file__))).resolve()
    build_in_wf = current_dir / "build_in_wf"
    for file in build_in_wf.iterdir():
        if file.is_file():
            shutil.copy(file, wf_dir)

if config.comfyui_audit_local:
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

logger.info(f"Comfyui插件加载完成, 配置: {config}")
