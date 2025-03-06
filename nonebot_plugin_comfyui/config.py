import os
import shutil
import yaml as yaml_
from ruamel.yaml import YAML

from nonebot import get_plugin_config, logger, get_driver
from pathlib import Path
from pydantic import BaseModel

PLUGIN_DIR = Path(os.path.dirname(os.path.abspath(__file__))).resolve()

config_file_path = Path("config/comfyui.yaml").resolve()
config_file_path_old = Path("config/comfyui_old.yaml").resolve()
source_template = PLUGIN_DIR / "template"  / "config.yaml"

destination_folder = Path("config")
destination_file = destination_folder / "comfyui.yaml"


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
    comfyui_text_audit: bool = False
    comfyui_audit_local: bool = False
    comfyui_audit_level: int = 2
    comfyui_audit_comp: bool = False
    comfyui_audit_site: str = "http://server.20020026.xyz:7865"
    comfyui_save_image: bool = True
    comfyui_cd: int = 20
    comfyui_day_limit: int = 50
    comfyui_limit_as_seconds: bool = False
    comfyui_timeout: int = 5
    comfyui_shape_preset: dict = {
        "p": (832, 1216),
        "l": (1216, 832),
        "s": (1024, 1024),
        "lp": (1152, 1536),
        "ll": (1536, 1152),
        "ls": (1240, 1240),
        "up": (960, 1920),
        "ul": (1920, 960)
    }
    comfyui_superusers: list = []
    comfyui_silent: bool = False
    comfyui_max_dict: dict = {"batch_size": 2, "batch_count": 2, "width": 2048, "height": 2048, "steps": 100}
    comfyui_http_proxy: str = os.environ.get("http_proxy")
    comfyui_openai: list = ["https://api.openai.com", "sk-xxxxxx"]
    comfyui_ai_prompt: bool = False
    comfyui_translate: bool = False
    comfyui_random_wf: bool = False
    comfyui_random_wf_list: list = ["txt2img"]
    comfyui_qr_mode: bool = False


def copy_config(source_template, destination_file):
    shutil.copy(source_template, destination_file)


def rewrite_yaml(old_config, source_template, delete_old=False):
    if delete_old:
        shutil.copy(config_file_path, config_file_path_old)
        os.remove(config_file_path)
    else:
        with open(source_template, 'r', encoding="utf-8") as f:
            yaml_data = yaml.load(f)
            for key, value in old_config.items():
                yaml_data[key] = value
        with open(config_file_path, 'w', encoding="utf-8") as f:
            yaml.dump(yaml_data, f)

    
def check_yaml_is_changed(source_template):
    with open(config_file_path, 'r', encoding="utf-8") as f:
        old = yaml.load(f)
    with open(source_template , 'r', encoding="utf-8") as f:
        example_ = yaml.load(f)
    keys1 = set(example_.keys())
    keys2 = set(old.keys())
    # print(f"{keys1}\n{keys2}")
    if keys1 == keys2:
        return False
    else:
        return True


yaml = YAML()
config = Config(**get_driver().config.model_dump())

if not config_file_path.exists():
    logger.info("配置文件不存在,正在创建")
    config_file_path.parent.mkdir(parents=True, exist_ok=True)
    copy_config(source_template, destination_file)
    rewrite_yaml(config.__dict__, source_template)
else:
    logger.info("配置文件存在,正在读取")
    if check_yaml_is_changed(source_template):
        logger.info("插件新的配置已更新,正在更新")
        with open(config_file_path, 'r', encoding="utf-8") as f:
            old_config = yaml.load(f)
        logger.warning(
'''
请注意新的配置文件从.env读取并且生成,旧的配置文件命名为comfyui_old.yaml,
此操作是为了确保插件新的功能能运行成功.
请手动前往复制更改到新的comfyui.yaml文件！！！
'''
        )
        rewrite_yaml(old_config, source_template, True)
        copy_config(source_template, destination_file)
        rewrite_yaml(config.__dict__, source_template)
    else:
        with open(config_file_path, "r", encoding="utf-8") as f:
            yaml_config = yaml_.load(f, Loader=yaml_.FullLoader)
            config = Config(**yaml_config)
            
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
            
    
logger.info(f"ComfyUI插件加载完成, 配置: {config}")
BACKEND_URL_LIST = config.comfyui_url_list