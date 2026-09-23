"""
nonebot-plugin-comfyui 异常定义体系
所有异常均继承自统一基类 ComfyuiExceptions (即 ComfyUIPluginError)，
确保支持统配捕获，并保留命名空间向后兼容。
"""

class ComfyuiExceptions(Exception):
    """插件基础异常类"""
    def __init__(self, message: str = "ComfyUI 插件异常"):
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


ComfyUIPluginError = ComfyuiExceptions


class NoAvailableBackendError(ComfyuiExceptions):
    def __init__(self, message: str = "没有可用后端, 所有后端掉线"):
        super().__init__(message)


class PostingFailedError(ComfyuiExceptions):
    def __init__(self, message: str = "Post服务器时出现错误"):
        super().__init__(message)


class ArgsError(ComfyuiExceptions):
    def __init__(self, message: str = "参数错误"):
        super().__init__(message)


class APIJsonError(ComfyuiExceptions):
    def __init__(self, message: str = "APIjson错误"):
        super().__init__(message)


class ReflexJsonError(ComfyuiExceptions):
    def __init__(self, message: str = "Reflex json错误"):
        super().__init__(message)


class InputFileNotFoundError(ComfyuiExceptions):
    def __init__(self, message: str = "未提供工作流需要的输入(例如图片)"):
        super().__init__(message)


class ReflexJsonOutputError(ReflexJsonError):
    def __init__(self, message: str = "Reflex json输出设置错误"):
        super().__init__(message)


class ReflexJsonNotFoundError(ReflexJsonError):
    def __init__(self, message: str = "未找到工作流对应的Reflex json!"):
        super().__init__(message)


class ComfyuiBackendConnectionError(ComfyuiExceptions):
    def __init__(self, message: str = "连接到comfyui后端出错"):
        super().__init__(message)


class GetResultError(ComfyuiExceptions):
    def __init__(self, message: str = "获取生成结果时出现错误"):
        super().__init__(message)


class AuditError(ComfyuiExceptions):
    def __init__(self, message: str = "图片审核失败"):
        super().__init__(message)


class TaskNotFoundError(ComfyuiExceptions):
    def __init__(self, message: str = "未找到提供的任务ID对应的任务"):
        super().__init__(message)


class InterruptError(ComfyuiExceptions):
    def __init__(self, message: str = "任务已被终止"):
        super().__init__(message)


class TaskError(ComfyuiExceptions):
    def __init__(self, message: str = "任务出错"):
        super().__init__(message)


class WorkflowNotAvailableInSelectedBackend(ComfyuiExceptions):
    def __init__(self, message: str = "所选的工作流不支持在所选后端上执行"):
        super().__init__(message)


class NoAvailableBackendForSelectedWorkflow(ComfyuiExceptions):
    def __init__(self, message: str = "目前没有可运行所选的工作流的后端"):
        super().__init__(message)


class TextContentNotSafeError(ComfyuiExceptions):
    def __init__(self, message: str = "文字内容检测到违规"):
        super().__init__(message)


class ReachWorkFlowExecLimitations(ComfyuiExceptions):
    def __init__(self, message: str = "超过此工作流调用次数限制, 今天无法再次使用此工作流"):
        super().__init__(message)


class SendImageToBotException(ComfyuiExceptions):
    def __init__(self, message: str = "机器人给自身发送图片获取图片url时失败"):
        super().__init__(message)


class WorkflowAdminLimitation(ComfyuiExceptions):
    def __init__(self, message: str = "此工作流不允许非管理员用户使用"):
        super().__init__(message)


class WorkflowGroupLimitation(ComfyuiExceptions):
    def __init__(self, message: str = "此工作流不允许在本群使用"):
        super().__init__(message)


class ComfyuiNotAvaInCurrentGroup(ComfyuiExceptions):
    def __init__(self, message: str = "本群不可以使用此插件"):
        super().__init__(message)


# 挂载子异常至基类，保持 ComfyuiExceptions.NoAvailableBackendError 语法兼容
ComfyuiExceptions.NoAvailableBackendError = NoAvailableBackendError
ComfyuiExceptions.PostingFailedError = PostingFailedError
ComfyuiExceptions.ArgsError = ArgsError
ComfyuiExceptions.APIJsonError = APIJsonError
ComfyuiExceptions.ReflexJsonError = ReflexJsonError
ComfyuiExceptions.InputFileNotFoundError = InputFileNotFoundError
ComfyuiExceptions.ReflexJsonOutputError = ReflexJsonOutputError
ComfyuiExceptions.ReflexJsonNotFoundError = ReflexJsonNotFoundError
ComfyuiExceptions.ComfyuiBackendConnectionError = ComfyuiBackendConnectionError
ComfyuiExceptions.GetResultError = GetResultError
ComfyuiExceptions.AuditError = AuditError
ComfyuiExceptions.TaskNotFoundError = TaskNotFoundError
ComfyuiExceptions.InterruptError = InterruptError
ComfyuiExceptions.TaskError = TaskError
ComfyuiExceptions.WorkflowNotAvailableInSelectedBackend = WorkflowNotAvailableInSelectedBackend
ComfyuiExceptions.NoAvailableBackendForSelectedWorkflow = NoAvailableBackendForSelectedWorkflow
ComfyuiExceptions.TextContentNotSafeError = TextContentNotSafeError
ComfyuiExceptions.ReachWorkFlowExecLimitations = ReachWorkFlowExecLimitations
ComfyuiExceptions.SendImageToBotException = SendImageToBotException
ComfyuiExceptions.WorkflowAdminLimitation = WorkflowAdminLimitation
ComfyuiExceptions.WorkflowGroupLimitation = WorkflowGroupLimitation
ComfyuiExceptions.ComfyuiNotAvaInCurrentGroup = ComfyuiNotAvaInCurrentGroup