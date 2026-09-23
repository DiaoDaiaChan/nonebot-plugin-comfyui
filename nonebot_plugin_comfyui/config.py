import os
import shutil
from pathlib import Path
from typing import Any
import yaml as pyyaml
try:
    from ruamel.yaml import YAML
except ImportError:
    YAML = None

from nonebot import logger, get_driver
from pydantic import BaseModel, Field

from .constants import DEFAULT_LLM_SYS_PROMPT, DEFAULT_LLM_CONVERSATIONS

PLUGIN_DIR: Path = Path(__file__).parent.resolve()
CONFIG_FILE_PATH: Path = Path("config/comfyui.yaml").resolve()
CONFIG_FILE_PATH_OLD: Path = Path("config/comfyui_old.yaml").resolve()
SOURCE_TEMPLATE: Path = PLUGIN_DIR / "template" / "config.yaml"
DESTINATION_FOLDER: Path = Path("config")
DESTINATION_FILE: Path = DESTINATION_FOLDER / "comfyui.yaml"


class Config(BaseModel):
    comfyui_url: str = "http://127.0.0.1:8188"
    comfyui_url_list: list[str] = ["http://127.0.0.1:8188", "http://127.0.0.1:8288"]
    comfyui_multi_backend: bool = False
    comfyui_model: str = ""
    comfyui_workflows_dir: str = "./data/comfyui"
    comfyui_default_workflows: str = "txt2img"
    comfyui_base_res: int = 1024
    comfyui_audit: bool = True
    comfyui_text_audit: bool = False
    comfyui_audit_local: bool = False
    comfyui_audit_model: int = 1
    comfyui_wd_model: dict[str, Any] = {
        "name": 'WaifuDiffusion',
        "repo_id": "wd-vit-tagger-v3",
        "revision": 'v2.0',
        "model_path": 'model.onnx',
        "tags_path": 'selected_tags.csv'
    }
    comfyui_dual_audit: bool = False
    comfyui_nude_model_path: str = ""
    comfyui_audit_gpu: bool = False
    comfyui_audit_level: int = 2
    comfyui_group_config: dict[str, dict] = {
        "audit_level_group": {},
        "reject_nsfw_prompts": {},
        "img_send": {},
        "enable_in_group": {},
        "pure": {}
    }
    comfyui_audit_comp: bool = False
    comfyui_audit_site: str = "http://server.20020026.xyz:7865"
    comfyui_save_image: bool = True
    comfyui_cd: int = 20
    comfyui_day_limit: int = 50
    comfyui_limit_as_seconds: bool = False
    comfyui_timeout: int = 5
    comfyui_shape_preset: dict[str, tuple[int, int]] = {
        "p": (832, 1216),
        "l": (1216, 832),
        "s": (1024, 1024),
        "lp": (1152, 1536),
        "ll": (1536, 1152),
        "ls": (1240, 1240),
        "up": (960, 1920),
        "ul": (1920, 960)
    }
    comfyui_superusers: list[Any] = Field(default_factory=list)
    comfyui_silent: bool = False
    comfyui_quiet: bool = False
    comfyui_max_dict: dict[str, int] = {
        "batch_size": 2,
        "batch_count": 2,
        "width": 2048,
        "height": 2048,
        "steps": 100
    }
    comfyui_http_proxy: str = ""
    comfyui_llm_prompt_preset: list[dict[str, Any]] = []
    comfyui_openai: dict[str, Any] = {
        "endpoint": "https://api.openai.com/v1",
        "token": "sk-xxxxxx",
        "params": {
            "model": "gpt-3.5-turbo",
            "temperature": 1,
            "top_p": 1,
            "frequency_penalty": 2,
            "presence_penalty": 2
        },
        "repeat_sys_prompt": False,
        "prompt": DEFAULT_LLM_SYS_PROMPT,
        "conversations": DEFAULT_LLM_CONVERSATIONS
    }
    comfyui_ai_prompt: bool = False
    comfyui_translate: bool = False
    trans_api: str = ""
    comfyui_random_wf: bool = False
    comfyui_random_wf_list: list[str] = ["txt2img"]
    comfyui_qr_mode: bool = False
    comfyui_random_params: dict[str, list[tuple[Any, float]]] = {
        "shape": [("p", 0.7), ("l", 0.15), ("s", 0.05), ("up", 0.05), ("ul", 0.05)]
    }
    comfyui_random_params_enable: bool = False
    comfyui_default_value: dict[str, Any] = {
        "width": 832,
        "height": 1216,
        "accept_ratio": None,
        "shape": None,
        "steps": 28,
        "cfg_scale": 7.0,
        "denoise_strength": 1.0,
        "sampler": "dpmpp_2m",
        "scheduler": "karras",
        "batch_size": 1,
        "batch_count": 1,
        "model": "",
        "override": False,
        "override_ng": False,
        "forward": False,
        "concurrency": False,
        "pure": False,
        "notice": False,
        "preset_prompt": "",
        "preset_negative_prompt": "",
        "llm_preset": 0
    }
    comfyui_auto_lora: bool = False
    comfyui_r18_action: int = 1
    comfyui_img_send: int = 1
    comfyui_ban_words: list[str] = []
    comfyui_trigger_word: list[str] = []
    comfyui_tips: list[str] = [
        "发送 comfyui帮助 来获取详细的操作",
        "queue -stop 可以停止当前生成",
        "插件默认不支持中文提示词",
        "插件帮助菜单中的注册的命令为可以调用的额外命令",
        "查看工作流，可以查看所有的工作流；查看工作流 flux，可以筛选带有flux的工作流",
        "使用 -con / -并发 参数进行多后端并发生图",
        "使用 -r 1216x832 参数, 可快速设定分辨率"
    ]


def _model_to_dict(model_obj: BaseModel) -> dict[str, Any]:
    if hasattr(model_obj, "model_dump"):
        return model_obj.model_dump()
    return model_obj.dict()


def load_plugin_config() -> Config:
    """安全读取配置，合并全局配置与本地 yaml 配置"""
    driver = get_driver()
    driver_dict: dict[str, Any] = {}
    if hasattr(driver.config, "model_dump"):
        driver_dict = driver.config.model_dump()
    elif hasattr(driver.config, "dict"):
        driver_dict = driver.config.dict()

    base_config = Config(**driver_dict)

    if CONFIG_FILE_PATH.exists():
        try:
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                yaml_data = pyyaml.load(f, Loader=pyyaml.FullLoader)
                if isinstance(yaml_data, dict):
                    if "comfyui_superusers" in yaml_data and isinstance(yaml_data["comfyui_superusers"], list):
                        yaml_data["comfyui_superusers"] = [str(x) for x in yaml_data["comfyui_superusers"] if x is not None]
                    base_config = Config(**yaml_data)
        except Exception as e:
            logger.error(f"读取 ComfyUI 配置文件失败: {e}")
    else:
        try:
            CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
            if SOURCE_TEMPLATE.exists():
                shutil.copy(SOURCE_TEMPLATE, CONFIG_FILE_PATH)
        except Exception as e:
            logger.warning(f"自动初始化 ComfyUI 配置文件模板失败: {e}")

    # 合并 superusers
    driver_superusers = list(getattr(driver.config, "superusers", []))
    base_config.comfyui_superusers = list(set(base_config.comfyui_superusers + driver_superusers))

    if not base_config.comfyui_multi_backend:
        base_config.comfyui_url_list = [base_config.comfyui_url]

    return base_config


def init_workflows_dir(workflows_dir_path: str | Path) -> None:
    """初始化内置工作流文件夹"""
    wf_dir = Path(workflows_dir_path).resolve()
    if not wf_dir.exists():
        wf_dir.mkdir(parents=True, exist_ok=True)
        build_in_wf = PLUGIN_DIR / "build_in_wf"
        if build_in_wf.exists():
            for file in build_in_wf.iterdir():
                if file.is_file():
                    shutil.copy(file, wf_dir)
            logger.info(f"已同步内置工作流到: {wf_dir}")


config: Config = load_plugin_config()
BACKEND_URL_LIST: list[str] = config.comfyui_url_list