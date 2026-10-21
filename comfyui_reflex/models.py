"""
comfyui_reflex.models
~~~~~~~~~~~~~~~~~~~~~
ComfyUI API 节点模型与 Reflex 规则配置对象。
纯 Python 标准库，无任何三方依赖，专用于 ComfyUI 工作流改写。
"""

import copy
import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any


class ComfyNode:
    """
    ComfyUI API JSON 节点的高级对象封装。
    代表一个拥有 ID、class_type 和 inputs 字典的图节点。
    """

    def __init__(self, node_id: str | int, data: dict[str, Any]):
        self.id: str = str(node_id)
        self._data: dict[str, Any] = data

    @property
    def class_type(self) -> str:
        """节点的类名称，例如 'KSampler', 'CLIPTextEncode'"""
        return str(self._data.get("class_type", ""))

    @class_type.setter
    def class_type(self, value: str) -> None:
        self._data["class_type"] = value

    @property
    def inputs(self) -> dict[str, Any]:
        """节点的输入字典引用"""
        if "inputs" not in self._data or not isinstance(self._data["inputs"], dict):
            self._data["inputs"] = {}
        return self._data["inputs"]

    @property
    def title(self) -> str | None:
        """节点标题（通常存储于 _meta.title）"""
        meta = self._data.get("_meta")
        if isinstance(meta, dict):
            return meta.get("title")
        return None

    @title.setter
    def title(self, value: str) -> None:
        if "_meta" not in self._data or not isinstance(self._data["_meta"], dict):
            self._data["_meta"] = {}
        self._data["_meta"]["title"] = value

    def get_input(self, name: str, default: Any = None) -> Any:
        """获取指定输入参数"""
        return self.inputs.get(name, default)

    def set_input(self, name: str, value: Any) -> "ComfyNode":
        """设置指定输入参数，支持链式调用"""
        self.inputs[name] = value
        return self

    def has_input(self, name: str) -> bool:
        """判断是否存在某个输入"""
        return name in self.inputs

    def incoming_links(self) -> dict[str, tuple[str, int]]:
        """
        获取所有指向该节点的上游连线输入。
        ComfyUI 格式为 {"slot_name": ["upstream_node_id", slot_index]}。
        返回 {"slot_name": (upstream_node_id, slot_index)}
        """
        links: dict[str, tuple[str, int]] = {}
        for k, v in self.inputs.items():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[1], int):
                links[k] = (str(v[0]), v[1])
        return links

    def to_dict(self) -> dict[str, Any]:
        """导出为原始 API JSON 格式节点字典"""
        return copy.deepcopy(self._data)

    def __repr__(self) -> str:
        return f"ComfyNode(id={self.id!r}, class_type={self.class_type!r}, title={self.title!r})"


class ReflexConfig(Mapping[str, Any]):
    """
    Reflex 规则定义强类型封装。
    用于指导工作流的改写映射规则（如采样器节点、提示词节点、尺寸节点、高级覆写动作等）。
    支持字典解构、只读访问与格式化校验。
    """

    def __init__(self, data: dict[str, Any] | None = None):
        self._data: dict[str, Any] = copy.deepcopy(data or {})

    @classmethod
    def from_file(cls, path: str | Path) -> "ReflexConfig":
        """从 JSON 文件加载 Reflex 配置"""
        p = Path(path)
        with open(p, "r", encoding="utf-8") as f:
            content = json.load(f)
        return cls(content)

    @classmethod
    def from_json(cls, json_str: str) -> "ReflexConfig":
        """从 JSON 字符串反序列化 Reflex 配置"""
        return cls(json.loads(json_str))

    @property
    def output_nodes(self) -> dict[str, list[str]]:
        """
        获取工作流声明的输出节点映射。
        规范化为 {media_type: [node_id, ...]} 格式。
        """
        out = self._data.get("output", [])
        media = str(self._data.get("media", "image"))

        if isinstance(out, list):
            return {media: [str(x) for x in out]}
        elif isinstance(out, dict):
            res: dict[str, list[str]] = {}
            for m_type, nodes in out.items():
                if isinstance(nodes, list):
                    res[str(m_type)] = [str(x) for x in nodes]
                else:
                    res[str(m_type)] = [str(nodes)]
            return res
        elif isinstance(out, (str, int)):
            return {media: [str(out)]}
        return {}

    @property
    def all_output_node_ids(self) -> list[str]:
        """获取所有输出节点的 ID 列表（去重）"""
        ids: list[str] = []
        for nodes in self.output_nodes.values():
            for n in nodes:
                if n not in ids:
                    ids.append(n)
        return ids

    @property
    def media_type(self) -> str:
        """主输出媒体类型，默认为 'image'，可为 'audio', 'video' 等"""
        return str(self._data.get("media", "image"))

    @property
    def output_prefix(self) -> str | None:
        """输出文件前缀"""
        return self._data.get("output_prefix")

    @property
    def requires_image(self) -> bool:
        """该工作流是否需要输入图片 (根据 load_image 字段判断)"""
        return bool(self._data.get("load_image"))

    @property
    def note(self) -> str:
        """工作流说明与备注文本"""
        return str(self._data.get("note", ""))

    @property
    def presets(self) -> dict[str, Any]:
        """工作流自带的预设形制或参数字典"""
        p = self._data.get("presets")
        return p if isinstance(p, dict) else {}

    @property
    def lora_config(self) -> Any:
        """LoRA 节点链插入配置"""
        return self._data.get("lora")

    @property
    def backend_reflex(self) -> dict[str, Any]:
        """针对不同后端或机型的差异化覆盖规则"""
        r = self._data.get("reflex")
        return r if isinstance(r, dict) else {}

    def to_dict(self) -> dict[str, Any]:
        """转换为标准字典副本"""
        return copy.deepcopy(self._data)

    def to_json(self, indent: int = 2) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(self._data, indent=indent, ensure_ascii=False)

    def save_to_file(self, path: str | Path, indent: int = 2) -> None:
        """保存到文件"""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(self.to_json(indent=indent))

    # Mapping 抽象基类方法实现
    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, key: object) -> bool:
        return key in self._data

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def __repr__(self) -> str:
        return f"ReflexConfig(media={self.media_type!r}, outputs={self.all_output_node_ids})"
