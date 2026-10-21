"""
comfyui_reflex.workflow
~~~~~~~~~~~~~~~~~~~~~~~
ComfyWorkflow: 面向对象、流式链式调用的 ComfyUI API 工作流核心改写操作类。
纯标准库实现，无任何三方依赖，专为高效、直观地改写 ComfyUI API Prompt 图而设计。
"""

import copy
import json
import random
from pathlib import Path
from typing import Any

from .constants import KNOWN_CLASS_TYPES, MAX_SEED, SAMPLER_MAPPING, SCHEDULER_MAPPING
from .dimensions import calculate_dimensions
from .engine import ReflexEngine
from .exceptions import NodeNotFoundError, WorkflowFormatError
from .lora import apply_loras_to_api_json
from .models import ComfyNode, ReflexConfig
from .png import extract_prompt_from_png


class ComfyWorkflow:
    """
    ComfyUI 工作流包装类。
    提供方便的节点检索、参数改写、LoRA 注入、链式调用以及序列化功能。
    """

    def __init__(self, data: dict[str, Any] | None = None):
        raw = data or {}
        if not isinstance(raw, dict):
            raise WorkflowFormatError("工作流数据必须是字典格式")
        self._nodes: dict[str, ComfyNode] = {}
        for nid, ndata in raw.items():
            if isinstance(ndata, dict):
                self._nodes[str(nid)] = ComfyNode(str(nid), copy.deepcopy(ndata))

    # =========================================================================
    # 加载与工厂方法
    # =========================================================================

    @classmethod
    def load(cls, path: str | Path) -> "ComfyWorkflow":
        """从 JSON 文件加载工作流 API Prompt"""
        p = Path(path)
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(data)

    @classmethod
    def from_file(cls, path: str | Path) -> "ComfyWorkflow":
        """load 的别名"""
        return cls.load(path)

    @classmethod
    def from_json(cls, json_str: str) -> "ComfyWorkflow":
        """从 JSON 文本加载"""
        return cls(json.loads(json_str))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ComfyWorkflow":
        """从原生 API JSON 字典构建"""
        return cls(data)

    @classmethod
    def from_image(cls, path_or_bytes: str | Path | bytes) -> "ComfyWorkflow":
        """直接从 ComfyUI 输出的 PNG 图像中提取 API JSON 工作流构建"""
        prompt = extract_prompt_from_png(path_or_bytes)
        return cls(prompt)

    def clone(self) -> "ComfyWorkflow":
        """深拷贝当前工作流，用于多分支试验改写"""
        return ComfyWorkflow(self.to_dict())

    # =========================================================================
    # 节点查找与访问
    # =========================================================================

    @property
    def nodes(self) -> dict[str, ComfyNode]:
        """所有节点的字典映射 {node_id: ComfyNode}"""
        return self._nodes

    def get_node(self, node_id: str | int) -> ComfyNode | None:
        """根据 ID 获取节点"""
        return self._nodes.get(str(node_id))

    def require_node(self, node_id: str | int) -> ComfyNode:
        """获取节点，不存在时抛出 NodeNotFoundError"""
        node = self.get_node(node_id)
        if not node:
            raise NodeNotFoundError(node_id)
        return node

    def has_node(self, node_id: str | int) -> bool:
        """判断节点是否存在"""
        return str(node_id) in self._nodes

    def find_nodes_by_class(self, class_type: str | set[str] | list[str]) -> list[ComfyNode]:
        """根据 class_type 查找所有匹配的节点"""
        types = {class_type} if isinstance(class_type, str) else set(class_type)
        return [node for node in self._nodes.values() if node.class_type in types]

    def find_first_by_class(self, class_type: str | set[str] | list[str]) -> ComfyNode | None:
        """根据 class_type 查找第一个匹配的节点"""
        matches = self.find_nodes_by_class(class_type)
        return matches[0] if matches else None

    def find_nodes_by_title(self, title: str) -> list[ComfyNode]:
        """根据标题 (_meta.title) 查找匹配节点"""
        return [node for node in self._nodes.values() if node.title == title]

    def find_first_by_title(self, title: str) -> ComfyNode | None:
        """根据标题查找第一个匹配节点"""
        matches = self.find_nodes_by_title(title)
        return matches[0] if matches else None

    def get_output_nodes(self) -> list[ComfyNode]:
        """
        查找所有输出节点（例如 SaveImage、PreviewImage、VHS_VideoCombine 等），
        或未被任何其他节点作为输入的末端节点。
        """
        known_saves = KNOWN_CLASS_TYPES["save_image"]
        outputs = [node for node in self._nodes.values() if node.class_type in known_saves]
        if outputs:
            return outputs

        # 如果没有识别到标准输出类，查找所有未被引用的终端节点
        referenced_ids = set()
        for node in self._nodes.values():
            for val in node.inputs.values():
                if isinstance(val, list) and len(val) == 2:
                    referenced_ids.add(str(val[0]))

        terminal_nodes = [node for nid, node in self._nodes.items() if nid not in referenced_ids]
        return terminal_nodes

    # =========================================================================
    # 图结构编辑与连线
    # =========================================================================

    def add_node(
        self,
        node_id: str | int,
        class_type: str,
        inputs: dict[str, Any] | None = None,
        title: str | None = None
    ) -> ComfyNode:
        """向工作流中添加或覆盖一个节点"""
        nid = str(node_id)
        data: dict[str, Any] = {
            "class_type": class_type,
            "inputs": copy.deepcopy(inputs or {})
        }
        if title:
            data["_meta"] = {"title": title}
        node = ComfyNode(nid, data)
        self._nodes[nid] = node
        return node

    def remove_node(self, node_id: str | int) -> ComfyNode | None:
        """从工作流中移除指定节点"""
        return self._nodes.pop(str(node_id), None)

    def link(
        self,
        from_node: str | int,
        from_slot: int,
        to_node: str | int,
        to_input: str
    ) -> "ComfyWorkflow":
        """在两个节点之间建立连接 [from_node, from_slot] -> to_node.inputs[to_input]"""
        target = self.require_node(to_node)
        target.set_input(to_input, [str(from_node), int(from_slot)])
        return self

    def unlink(self, to_node: str | int, to_input: str) -> "ComfyWorkflow":
        """断开指定输入的连线"""
        target = self.get_node(to_node)
        if target and to_input in target.inputs:
            del target.inputs[to_input]
        return self

    # =========================================================================
    # 常用高阶流式改写方法 (Fluent API)
    # =========================================================================

    def set_prompt(self, text: str, node_id: str | int | None = None) -> "ComfyWorkflow":
        """
        设置正向提示词。
        若未指定 node_id，则自动探测 CLIPTextEncode 类型的节点。
        """
        if node_id:
            node = self.require_node(node_id)
            node.set_input("text", text)
            return self

        # 智能查找：先找 title 包含 positive 或正向的
        for n in self.find_nodes_by_class(KNOWN_CLASS_TYPES["text_encode"]):
            if n.title and ("pos" in n.title.lower() or "正向" in n.title):
                n.set_input("text", text)
                return self

        # 退回到第一个 text encode 节点
        first_encode = self.find_first_by_class(KNOWN_CLASS_TYPES["text_encode"])
        if first_encode:
            first_encode.set_input("text", text)
        return self

    def set_negative_prompt(self, text: str, node_id: str | int | None = None) -> "ComfyWorkflow":
        """
        设置负向提示词。
        若未指定 node_id，则自动探测负向 CLIPTextEncode 节点。
        """
        if node_id:
            node = self.require_node(node_id)
            node.set_input("text", text)
            return self

        for n in self.find_nodes_by_class(KNOWN_CLASS_TYPES["text_encode"]):
            if n.title and ("neg" in n.title.lower() or "负向" in n.title or "反向" in n.title):
                n.set_input("text", text)
                return self

        # 如果存在多个 text_encode，第二个通常为负向
        all_encoders = self.find_nodes_by_class(KNOWN_CLASS_TYPES["text_encode"])
        if len(all_encoders) >= 2:
            all_encoders[1].set_input("text", text)
        return self

    def append_prompt(self, additional_text: str, node_id: str | int | None = None) -> "ComfyWorkflow":
        """在现有正向提示词后追加文本"""
        target = self.require_node(node_id) if node_id else self.find_first_by_class(KNOWN_CLASS_TYPES["text_encode"])
        if target:
            curr = str(target.get_input("text", ""))
            delimiter = ", " if curr and not curr.endswith(",") else ""
            target.set_input("text", curr + delimiter + additional_text)
        return self

    def replace_prompt_placeholder(
        self,
        token: str,
        replacement: str,
        node_id: str | int | None = None
    ) -> "ComfyWorkflow":
        """替换提示词中的占位符 (例如 '{prompt}')"""
        target = self.require_node(node_id) if node_id else self.find_first_by_class(KNOWN_CLASS_TYPES["text_encode"])
        if target:
            curr = str(target.get_input("text", ""))
            target.set_input("text", curr.replace(token, replacement))
        return self

    def set_seed(self, seed: int, node_id: str | int | None = None) -> "ComfyWorkflow":
        """
        设置随机种子。
        若未指定 node_id，则自动设置所有 KSampler、KSamplerAdvanced 及种子相关节点。
        """
        if node_id:
            node = self.require_node(node_id)
            if node.has_input("seed"):
                node.set_input("seed", seed)
            if node.has_input("noise_seed"):
                node.set_input("noise_seed", seed)
            return self

        for node in self.find_nodes_by_class(KNOWN_CLASS_TYPES["sampler"]):
            if node.has_input("seed"):
                node.set_input("seed", seed)
            if node.has_input("noise_seed"):
                node.set_input("noise_seed", seed)
        return self

    def randomize_seeds(self, max_seed: int = MAX_SEED) -> "ComfyWorkflow":
        """将工作流中所有采样器节点的种子随机化"""
        new_seed = random.randint(0, max_seed)
        return self.set_seed(new_seed)

    def set_sampler(
        self,
        node_id: str | int | None = None,
        seed: int | None = None,
        steps: int | None = None,
        cfg: float | None = None,
        sampler_name: str | None = None,
        scheduler: str | None = None,
        denoise: float | None = None
    ) -> "ComfyWorkflow":
        """
        配置采样器参数。自动转换人类可读名称（如 'Euler a' -> 'euler_ancestral'）。
        """
        target = self.require_node(node_id) if node_id else self.find_first_by_class(KNOWN_CLASS_TYPES["sampler"])
        if not target:
            return self

        if seed is not None:
            if target.has_input("seed"):
                target.set_input("seed", seed)
            if target.has_input("noise_seed"):
                target.set_input("noise_seed", seed)
        if steps is not None:
            target.set_input("steps", steps)
        if cfg is not None:
            target.set_input("cfg", cfg)
        if sampler_name is not None:
            normalized_s = SAMPLER_MAPPING.get(sampler_name, sampler_name)
            target.set_input("sampler_name", normalized_s)
        if scheduler is not None:
            normalized_sch = SCHEDULER_MAPPING.get(scheduler, scheduler)
            target.set_input("scheduler", normalized_sch)
        if denoise is not None:
            target.set_input("denoise", denoise)

        return self

    def set_dimensions(
        self,
        width: int,
        height: int,
        batch_size: int | None = None,
        node_id: str | int | None = None
    ) -> "ComfyWorkflow":
        """设置潜空间/图像尺寸（width, height, batch_size）"""
        target = self.require_node(node_id) if node_id else self.find_first_by_class(KNOWN_CLASS_TYPES["image_size"])
        if target:
            target.set_input("width", int(width))
            target.set_input("height", int(height))
            if batch_size is not None:
                target.set_input("batch_size", int(batch_size))
        return self

    def set_dimensions_by_ratio(
        self,
        shape: str | None = None,
        accept_ratio: str | None = None,
        base_res: int = 1024,
        batch_size: int | None = None,
        node_id: str | int | None = None
    ) -> "ComfyWorkflow":
        """根据形制预设 ('p'/'l'/'s'/'512x768') 或宽高比 ('16:9') 计算并设置分辨率"""
        w, h = calculate_dimensions(shape=shape, accept_ratio=accept_ratio, base_res=base_res)
        return self.set_dimensions(width=w, height=h, batch_size=batch_size, node_id=node_id)

    def set_checkpoint(self, ckpt_name: str, node_id: str | int | None = None) -> "ComfyWorkflow":
        """设置主模型/Checkpoint 文件名"""
        target = self.require_node(node_id) if node_id else self.find_first_by_class(KNOWN_CLASS_TYPES["checkpoint"])
        if target:
            if target.has_input("ckpt_name"):
                target.set_input("ckpt_name", ckpt_name)
            elif target.has_input("unet_name"):
                target.set_input("unet_name", ckpt_name)
            elif target.has_input("model"):
                target.set_input("model", ckpt_name)
        return self

    def set_input_image(self, image_name: str, node_id: str | int | None = None) -> "ComfyWorkflow":
        """设置输入的图片文件名 (LoadImage)"""
        target = self.require_node(node_id) if node_id else self.find_first_by_class(KNOWN_CLASS_TYPES["load_image"])
        if target:
            target.set_input("image", image_name)
        return self

    def inject_lora(
        self,
        lora_name: str,
        strength_model: float = 1.0,
        strength_clip: float | None = None,
        lora_config: Any = None
    ) -> "ComfyWorkflow":
        """在图结构中插入单个 LoRA 节点链"""
        str_clip = strength_model if strength_clip is None else strength_clip
        return self.inject_loras([(lora_name, strength_model)], lora_config=lora_config)

    def inject_loras(
        self,
        loras: list[tuple[str, float]],
        lora_config: Any = None
    ) -> "ComfyWorkflow":
        """
        根据 lora_config 或自动检测 CheckpointLoader，将多个 LoRA 串联注入 API 图。
        """
        if not loras:
            return self

        # 若未提供显式 lora_config，尝试查找主 checkpoint 作为起点
        cfg = lora_config
        if cfg is None:
            ckpt_node = self.find_first_by_class(KNOWN_CLASS_TYPES["checkpoint"])
            if ckpt_node:
                cfg = ckpt_node.id

        if cfg is not None:
            updated_dict = apply_loras_to_api_json(self.to_dict(), cfg, loras)
            # 重新同步内部节点集合
            self._nodes.clear()
            for nid, ndata in updated_dict.items():
                self._nodes[str(nid)] = ComfyNode(str(nid), copy.deepcopy(ndata))

        return self

    # =========================================================================
    # 声明式 Reflex 规则改写
    # =========================================================================

    def apply_reflex(
        self,
        reflex: ReflexConfig | dict[str, Any] | str | Path,
        params: dict[str, Any],
        init_images: list[dict[str, Any]] | None = None,
        backend_index: int = 0
    ) -> "ComfyWorkflow":
        """
        通过 Reflex 规则文件/字典改写当前工作流。
        应用包括基础参数映射、高级动作 (randint/upscale/append/replace)、
        reg_args 动态绑定、backend 差异覆盖及 LoRA 注入等。
        """
        if isinstance(reflex, (str, Path)):
            reflex_cfg = ReflexConfig.from_file(reflex).to_dict()
        elif isinstance(reflex, ReflexConfig):
            reflex_cfg = reflex.to_dict()
        else:
            reflex_cfg = reflex

        modified_dict = ReflexEngine.apply_reflex(
            raw_api_json=self.to_dict(),
            reflex_json=reflex_cfg,
            params=params,
            init_images=init_images,
            backend_index=backend_index
        )

        self._nodes.clear()
        for nid, ndata in modified_dict.items():
            self._nodes[str(nid)] = ComfyNode(str(nid), copy.deepcopy(ndata))
        return self

    # =========================================================================
    # 序列化与输出
    # =========================================================================

    def to_dict(self) -> dict[str, Any]:
        """导出为标准的 ComfyUI API Prompt JSON 字典"""
        return {nid: node.to_dict() for nid, node in self._nodes.items()}

    def to_prompt_payload(
        self,
        client_id: str | None = None,
        extra_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        构造可直接提交至 ComfyUI HTTP /prompt 接口的 Payload 格式：
        {"prompt": { ... }, "client_id": "...", "extra_data": { ... }}
        """
        payload: dict[str, Any] = {"prompt": self.to_dict()}
        if client_id is not None:
            payload["client_id"] = str(client_id)
        if extra_data:
            payload["extra_data"] = copy.deepcopy(extra_data)
        return payload

    def to_json(self, indent: int = 2) -> str:
        """导出为格式化 JSON 字符串"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def save(self, path: str | Path, indent: int = 2) -> None:
        """将当前工作流保存为 JSON 文件"""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(self.to_json(indent=indent))

    # Python 操作符支持
    def __getitem__(self, node_id: str | int) -> ComfyNode:
        return self.require_node(node_id)

    def __setitem__(self, node_id: str | int, node_or_dict: ComfyNode | dict[str, Any]) -> None:
        nid = str(node_id)
        if isinstance(node_or_dict, ComfyNode):
            self._nodes[nid] = node_or_dict
        else:
            self._nodes[nid] = ComfyNode(nid, copy.deepcopy(node_or_dict))

    def __delitem__(self, node_id: str | int) -> None:
        self.remove_node(node_id)

    def __contains__(self, node_id: object) -> bool:
        return str(node_id) in self._nodes

    def __len__(self) -> int:
        return len(self._nodes)

    def __iter__(self):
        return iter(self._nodes)

    def __repr__(self) -> str:
        return f"ComfyWorkflow(nodes={len(self._nodes)})"
