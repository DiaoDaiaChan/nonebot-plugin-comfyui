"""
comfyui_reflex.constants
~~~~~~~~~~~~~~~~~~~~~~~~
ComfyUI API 核心常量、动作标识与采样器/调度器标准映射表。
纯 Python 标准库，无任何三方依赖。
"""

# ComfyUI 最大随机种子 (2^31 - 1 或 2^31)
MAX_SEED: int = 2 ** 31

# 默认分辨率相关基准与形制预设
DEFAULT_BASE_RES: int = 1024
DEFAULT_WIDTH: int = 832
DEFAULT_HEIGHT: int = 1216

DEFAULT_SHAPE_PRESETS: dict[str, tuple[int, int]] = {
    "p": (832, 1216),    # 竖图 (portrait)
    "l": (1216, 832),    # 横图 (landscape)
    "s": (1024, 1024),   # 方图 (square)
    "ss": (512, 512),    # 小方图
    "w": (1216, 832),    # 宽图
}

# Reflex 规则中非直接节点映射的保留配置键 (纯工作流相关，无机器人概念)
OTHER_ACTION: set[str] = {
    "override",
    "note",
    "presets",
    "media",
    "reg_args",
    "output_prefix",
    "lora",
    "available",
    "reflex",
    "only_available"
}

# 节点高级覆写支持的动作
OVERRIDE_SUPPORT_KEYS: set[str] = {
    "keep",
    "value",
    "append_prompt",
    "append_negative_prompt",
    "replace_prompt",
    "replace_negative_prompt",
    "remove",
    "randint",
    "get_text",
    "upscale",
    "image"
}

# 修改型动作键
MODIFY_ACTION: set[str] = {"output", "reg_args"}

# 常见采样器与调度器名称标准化映射
SAMPLER_MAPPING: dict[str, str] = {
    "DPM++ 2M": "dpmpp_2m",
    "DPM++ SDE": "dpmpp_sde",
    "DPM++ 2M SDE": "dpmpp_2m_sde",
    "DPM++ 2M SDE Heun": "dpmpp_2m_sde",
    "DPM++ 2S a": "dpmpp_2s_ancestral",
    "DPM++ 3M SDE": "dpmpp_3m_sde",
    "Euler a": "euler_ancestral",
    "Euler": "euler",
    "LMS": "lms",
    "Heun": "heun",
    "DPM2": "dpm_2",
    "DPM2 a": "dpm_2_ancestral",
    "DPM fast": "dpm_fast",
    "DPM adaptive": "dpm_adaptive",
    "Restart": "restart",
    "HeunPP2": "heunpp2",
    "IPNDM": "ipndm",
    "IPNDM_V": "ipndm_v",
    "DEIS": "deis",
    "DDIM": "ddim",
    "DDIM CFG++": "ddim",
    "PLMS": "plms",
    "UniPC": "uni_pc",
    "LCM": "lcm",
    "DDPM": "ddpm",
}

SCHEDULER_MAPPING: dict[str, str] = {
    "Automatic": "normal",
    "Karras": "karras",
    "Exponential": "exponential",
    "SGM Uniform": "sgm_uniform",
    "Simple": "simple",
    "Normal": "normal",
    "DDIM": "ddim_uniform",
    "Beta": "beta"
}

REFLEX_DICT: dict[str, dict[str, str]] = {
    "sampler": SAMPLER_MAPPING,
    "scheduler": SCHEDULER_MAPPING
}

# 常见 ComfyUI 节点 ClassType 清单（用于智能探测节点）
KNOWN_CLASS_TYPES = {
    "sampler": {"KSampler", "KSamplerAdvanced"},
    "text_encode": {"CLIPTextEncode", "CLIPTextEncodeSDXL", "BNK_CLIPTextEncodeAdvanced"},
    "image_size": {"EmptyLatentImage", "EmptySD3LatentImage", "EmptyLatentImagePresets"},
    "checkpoint": {"CheckpointLoaderSimple", "CheckpointLoader", "UNETLoader"},
    "load_image": {"LoadImage", "LoadImageMask"},
    "save_image": {"SaveImage", "PreviewImage", "SaveImageWebp", "VHS_VideoCombine"},
    "lora_loader": {"LoraLoader", "LoraLoaderModelOnly"}
}
