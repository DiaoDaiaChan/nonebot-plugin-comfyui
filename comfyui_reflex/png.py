"""
comfyui_reflex.png
~~~~~~~~~~~~~~~~~~
纯标准库实现的 ComfyUI PNG 图像元数据提取器。
可直接从 ComfyUI 生成的 PNG 图片中提取 API JSON (prompt) 和 WebUI 工作流 (workflow)，
无需安装 Pillow / PIL 或任何三方图像库。
"""

import json
import struct
import zlib
from pathlib import Path
from typing import Any

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def read_png_text_chunks(source: str | Path | bytes) -> dict[str, str]:
    """
    读取 PNG 文件中的所有 tEXt 与 iTXt 文本元数据块。
    返回 {keyword: text} 映射。
    """
    if isinstance(source, (str, Path)):
        with open(source, "rb") as f:
            data = f.read()
    else:
        data = source

    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("输入数据不是有效的 PNG 图像文件")

    text_chunks: dict[str, str] = {}
    offset = 8
    total_len = len(data)

    while offset + 8 <= total_len:
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        chunk_type = data[offset + 4:offset + 8]
        offset += 8

        if offset + length + 4 > total_len:
            break

        chunk_data = data[offset:offset + length]
        offset += length + 4  # 跳过 chunk 数据和 4 字节 CRC

        if chunk_type == b"tEXt":
            null_pos = chunk_data.find(b"\x00")
            if null_pos != -1:
                keyword = chunk_data[:null_pos].decode("latin-1", errors="ignore")
                text = chunk_data[null_pos + 1:].decode("utf-8", errors="ignore")
                text_chunks[keyword] = text

        elif chunk_type == b"iTXt":
            null_pos = chunk_data.find(b"\x00")
            if null_pos != -1:
                keyword = chunk_data[:null_pos].decode("utf-8", errors="ignore")
                idx = null_pos + 1
                if idx + 2 <= len(chunk_data):
                    comp_flag = chunk_data[idx]
                    # comp_method = chunk_data[idx + 1]
                    idx += 2
                    # 跳过 language tag
                    next_null = chunk_data.find(b"\x00", idx)
                    if next_null != -1:
                        idx = next_null + 1
                    # 跳过 translated keyword
                    next_null = chunk_data.find(b"\x00", idx)
                    if next_null != -1:
                        idx = next_null + 1

                    raw_text = chunk_data[idx:]
                    if comp_flag == 1:
                        try:
                            text = zlib.decompress(raw_text).decode("utf-8", errors="ignore")
                        except Exception:
                            text = ""
                    else:
                        text = raw_text.decode("utf-8", errors="ignore")
                    text_chunks[keyword] = text

        elif chunk_type == b"IEND":
            break

    return text_chunks


def extract_comfyui_metadata_from_png(source: str | Path | bytes) -> dict[str, Any]:
    """
    从 ComfyUI 输出的 PNG 图片中提取完整元数据。
    返回字典，可能包含:
      - "prompt": dict (即 ComfyUI API JSON 格式)
      - "workflow": dict (即 ComfyUI WebUI 工作流图格式)
      - 以及其它附加文本键值
    """
    raw_chunks = read_png_text_chunks(source)
    result: dict[str, Any] = {}

    for k, v in raw_chunks.items():
        if k in ("prompt", "workflow"):
            try:
                result[k] = json.loads(v)
            except Exception:
                result[k] = v
        else:
            result[k] = v

    return result


def extract_prompt_from_png(source: str | Path | bytes) -> dict[str, Any]:
    """
    直接从 PNG 提取 ComfyUI API JSON (prompt)。
    若未包含则抛出 ValueError。
    """
    meta = extract_comfyui_metadata_from_png(source)
    prompt = meta.get("prompt")
    if not prompt or not isinstance(prompt, dict):
        raise ValueError("该 PNG 图片未包含有效的 ComfyUI API Prompt 元数据")
    return prompt
