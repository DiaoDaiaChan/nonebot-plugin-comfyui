"""
向后兼容模块：backend/wd_audit.py
实现已迁移至 nonebot_plugin_comfyui.services.audit.local_wd
"""
from ..services.audit.local_wd import local_wd_auditor

__all__ = ["local_wd_auditor"]
