from pathlib import Path
from typing import Any

from comfyui_reflex import (
    WorkflowLoader,
    ReflexEngine,
    ComfyWorkflow,
    calculate_dimensions as _calculate_dimensions
)
from comfyui_reflex.exceptions import (
    ReflexNotFoundError,
    ReflexConfigError,
    ReflexArgumentError
)

from ..config import config
from ..exceptions import (
    ReflexJsonNotFoundError,
    ReflexJsonError,
    WorkflowAdminLimitation,
    WorkflowGroupLimitation,
    ArgsError
)


class WorkflowEngine:
    """工作流检索、Reflex 规则应用与 API JSON 图重构引擎 (核心业务已解耦至 comfyui_reflex)"""

    @staticmethod
    def get_workflows_dir() -> Path:
        return Path(config.comfyui_workflows_dir).resolve()

    @classmethod
    def list_workflows(cls, search: str | None = None, index: int | None = None) -> list[str]:
        """列出或筛选所有合法的工作流名称"""
        return WorkflowLoader.list_workflows(cls.get_workflows_dir(), search=search, index=index)

    @classmethod
    async def load_workflow_files(cls, wf_name: str) -> tuple[dict[str, Any], dict[str, Any]]:
        """异步加载工作流 API JSON 和对应的 Reflex JSON"""
        try:
            return await WorkflowLoader.load_workflow_pair_async(
                workflows_dir=cls.get_workflows_dir(),
                wf_name=wf_name
            )
        except ReflexNotFoundError as e:
            raise ReflexJsonNotFoundError(str(e)) from e
        except ReflexConfigError as e:
            raise ReflexJsonError(str(e)) from e

    @staticmethod
    def calculate_dimensions(
        shape: str | None = None,
        accept_ratio: str | None = None,
        width: int | None = None,
        height: int | None = None
    ) -> tuple[int, int]:
        """统一计算分辨率"""
        try:
            return _calculate_dimensions(
                shape=shape,
                accept_ratio=accept_ratio,
                width=width,
                height=height,
                shape_presets=config.comfyui_shape_preset,
                base_res=config.comfyui_base_res,
                default_width=config.comfyui_default_value.get("width", 832),
                default_height=config.comfyui_default_value.get("height", 1216)
            )
        except ReflexArgumentError as e:
            raise ArgsError(str(e)) from e

    @classmethod
    def validate_permissions(
        cls,
        reflex_json: dict[str, Any],
        user_id: str,
        group_id: str
    ) -> None:
        """校验工作流的管理员与群组权限 (Bot 宿主业务)"""
        is_admin = reflex_json.get('admin', False)
        if is_admin and user_id not in config.comfyui_superusers:
            raise WorkflowAdminLimitation("此工作流仅限管理员使用")

        allowed_groups = reflex_json.get('group')
        if allowed_groups and group_id:
            try:
                gid_int = int(group_id)
                if gid_int not in allowed_groups:
                    raise WorkflowGroupLimitation("此工作流不允许在当前群使用")
            except ValueError:
                pass

    @classmethod
    def apply_reflex(
        cls,
        raw_api_json: dict[str, Any],
        reflex_json: dict[str, Any],
        params: dict[str, Any],
        init_images: list[dict[str, Any]] | None = None,
        backend_index: int = 0
    ) -> dict[str, Any]:
        """将生成参数应用到 API JSON 图中"""
        return ReflexEngine.apply_reflex(
            raw_api_json=raw_api_json,
            reflex_json=reflex_json,
            params=params,
            init_images=init_images,
            backend_index=backend_index
        )


workflow_engine = WorkflowEngine()
