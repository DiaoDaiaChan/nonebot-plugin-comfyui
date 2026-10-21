"""
comfyui-reflex
~~~~~~~~~~~~~~
A lightweight, pure Python standard library designed for manipulating,
inspecting, and rewriting ComfyUI API workflows.

Zero third-party dependencies.
"""

__version__ = "0.1.0"

from .constants import (
    KNOWN_CLASS_TYPES,
    MAX_SEED,
    MODIFY_ACTION,
    OTHER_ACTION,
    OVERRIDE_SUPPORT_KEYS,
    REFLEX_DICT,
    SAMPLER_MAPPING,
    SCHEDULER_MAPPING,
)
from .dimensions import calculate_dimensions
from .engine import ReflexEngine
from .exceptions import (
    NodeNotFoundError,
    ReflexArgumentError,
    ReflexConfigError,
    ReflexError,
    ReflexNotFoundError,
    WorkflowFormatError,
)
from .loader import WorkflowLoader
from .lora import (
    LORA_NODE_TEMPLATE,
    apply_loras_to_api_json,
    extract_loras_from_prompt,
)
from .models import ComfyNode, ReflexConfig
from .png import (
    extract_comfyui_metadata_from_png,
    extract_prompt_from_png,
    read_png_text_chunks,
)
from .workflow import ComfyWorkflow

__all__ = [
    "__version__",
    # 核心工作流对象
    "ComfyWorkflow",
    "ComfyNode",
    "ReflexConfig",
    "ReflexEngine",
    "WorkflowLoader",
    # 辅助纯函数
    "calculate_dimensions",
    "extract_loras_from_prompt",
    "apply_loras_to_api_json",
    # PNG 元数据提取
    "extract_prompt_from_png",
    "extract_comfyui_metadata_from_png",
    "read_png_text_chunks",
    # 常量
    "MAX_SEED",
    "SAMPLER_MAPPING",
    "SCHEDULER_MAPPING",
    "REFLEX_DICT",
    "OTHER_ACTION",
    "OVERRIDE_SUPPORT_KEYS",
    "MODIFY_ACTION",
    "KNOWN_CLASS_TYPES",
    "LORA_NODE_TEMPLATE",
    # 异常
    "ReflexError",
    "ReflexNotFoundError",
    "ReflexConfigError",
    "ReflexArgumentError",
    "NodeNotFoundError",
    "WorkflowFormatError",
]
