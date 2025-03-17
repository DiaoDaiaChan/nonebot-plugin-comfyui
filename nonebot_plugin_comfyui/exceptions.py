

class ComfyuiExceptions(BaseException):

    class NoAvailableBackendError(Exception):
        def __init__(self, message="没有可用后端, 所有后端掉线"):
            super().__init__(message)

    class PostingFailedError(Exception):
        def __init__(self, message="Post服务器时出现错误"):
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

    class TaskError(Exception):
        def __init__(self, message="任务出错"):
            super().__init__(message)
            
    class WorkflowNotAvailableInSelectedBackend(Exception):
        def __init__(self, message="所选的工作流不支持在所选后端上执行"):
            super().__init__(message)
            
    class NoAvailableBackendForSelectedWorkflow(Exception):
        def __init__(self, message="目前没有可运行所选的工作流的后端"):
            super().__init__(message)

    class TextContentNotSafeError(Exception):
        def __init__(self, message="文字内容检测到违规"):
            super().__init__(message)

    class ReachWorkFlowExecLimitations(Exception):
        def __init__(self, message="超过此工作流调用次数限制, 今天无法再次使用此工作流"):
            super().__init__(message)
    
    class WorkflowProcessingError(Exception):
        def __init__(self, message):
            super().__init__(message)
