"""
comfyui_reflex.exceptions
~~~~~~~~~~~~~~~~~~~~~~~~~
ComfyUI 工作流操作与 Reflex 规则引擎异常体系。
纯标准库实现，支持独立捕获并可被调用方多继承。
"""


class ReflexError(Exception):
    """Reflex 工作流操作基础异常类"""
    def __init__(self, message: str = "ComfyUI 工作流操作异常"):
        super().__init__(message)
        self.message = message


class ReflexNotFoundError(ReflexError):
    """未找到工作流定义或关联的 reflex 规则文件"""
    def __init__(self, message: str = "未找到指定的工作流定义或 reflex 文件"):
        super().__init__(message)


class ReflexConfigError(ReflexError):
    """Reflex 规则配置格式不正确或结构损坏"""
    def __init__(self, message: str = "Reflex 工作流规则配置错误"):
        super().__init__(message)


class ReflexArgumentError(ReflexError):
    """工作流计算参数（形制、宽高比、步数等）无效"""
    def __init__(self, message: str = "工作流参数计算或输入错误"):
        super().__init__(message)


class NodeNotFoundError(ReflexError):
    """在 API JSON 图结构中未找到目标节点"""
    def __init__(self, node_id: str | int, message: str | None = None):
        msg = message or f"在工作流中未找到节点 ID: {node_id}"
        super().__init__(msg)
        self.node_id = str(node_id)


class WorkflowFormatError(ReflexError):
    """工作流不是合法的 ComfyUI API JSON 格式"""
    def __init__(self, message: str = "工作流文件非有效 ComfyUI API Prompt JSON 格式"):
        super().__init__(message)
