

class ComfyuiExceptions(BaseException):

    class NoAvailableBackendError(Exception):
        def __init__(self, message="没有可用后端"):
            super().__init__(message)

    class PostingFailedError(Exception):
        def __init__(self, message="Post服务器试出现错误"):
            super().__init__(message)

    class ArgsError(Exception):
        def __init__(self, message="参数错误"):
            super().__init__(message)

    class APIJsonError(Exception):
        def __init__(self, message="APIjson错误"):
            super().__init__(message)

    class ReflexJsonError(Exception):
        def __init__(self, message="Reflex json错误"):
            super().__init__(message)

    class InputFileNotFoundError(Exception):
        def __init__(self, message="未提供工作流需要的输入(例如图片)"):
            super().__init__(message)

    class ReflexJsonOutputError(ReflexJsonError):
        def __init__(self, message="Reflex json输出设置错误"):
            super().__init__(message)

    class ReflexJsonNotFoundError(ReflexJsonError):
        def __init__(self, message="未找到工作流对应的Reflex json!"):
            super().__init__(message)

    class ComfyuiBackendConnectionError(Exception):
        def __init__(self, message="连接到comfyui后端出错"):
            super().__init__(message)

    class GetResultError(Exception):
        def __init__(self, message="获取生成结果时出现错误"):
            super().__init__(message)

    class AuditError(Exception):
        def __init__(self, message="图片审核失败"):
            super().__init__(message)

    class TaskNotFoundError(Exception):
        def __init__(self, message="未找到提供的任务ID对应的任务"):
            super().__init__(message)

    class InterruptError(Exception):
        def __init__(self, message="任务已被终止"):
            super().__init__(message)



