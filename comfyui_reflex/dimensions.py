"""
Resolution and aspect ratio calculation utilities for ComfyUI workflows.
"""

from typing import Mapping
from .constants import DEFAULT_SHAPE_PRESETS, DEFAULT_BASE_RES, DEFAULT_WIDTH, DEFAULT_HEIGHT
from .exceptions import ReflexArgumentError


def calculate_dimensions(
    shape: str | None = None,
    accept_ratio: str | None = None,
    width: int | None = None,
    height: int | None = None,
    shape_presets: Mapping[str, tuple[int, int]] | None = None,
    base_res: int = DEFAULT_BASE_RES,
    default_width: int = DEFAULT_WIDTH,
    default_height: int = DEFAULT_HEIGHT
) -> tuple[int, int]:
    """
    统一计算图像分辨率。
    
    优先级：
    1. 预设或自定义形制 shape（如 "p", "l", "s", "1024x768"）
    2. 画幅比例 accept_ratio（如 "16:9", "1:1"），基于 base_res 计算总像素并推导高宽
    3. 传入的 width/height 或默认宽高
    """
    presets = shape_presets if shape_presets is not None else DEFAULT_SHAPE_PRESETS

    # 1. 优先根据预设形制 shape 计算
    if shape:
        preset = presets.get(shape)
        if preset:
            return preset[0], preset[1]
        if 'x' in shape:
            try:
                w_s, h_s = shape.split('x')
                return int(w_s), int(h_s)
            except ValueError:
                pass

    # 2. 根据比例 accept_ratio 计算 (例如 16:9)
    if accept_ratio:
        if ':' in accept_ratio:
            try:
                w_ratio, h_ratio = map(int, accept_ratio.split(':'))
                if w_ratio <= 0 or h_ratio <= 0:
                    raise ValueError("Ratio components must be positive integers")
                total_pixels = base_res ** 2
                aspect = w_ratio / h_ratio
                if aspect >= 1:
                    w = int((total_pixels * aspect) ** 0.5)
                    h = int(w / aspect)
                else:
                    h = int((total_pixels / aspect) ** 0.5)
                    w = int(h * aspect)
                return w, h
            except Exception as e:
                raise ReflexArgumentError(f"画幅比例参数无效: {accept_ratio}") from e
        else:
            raise ReflexArgumentError(f"画幅比例参数格式错误 (应形如 W:H): {accept_ratio}")

    # 3. 默认宽与高
    w = width or default_width
    h = height or default_height
    return w, h
