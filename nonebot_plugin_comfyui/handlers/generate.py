import asyncio
import hashlib
import json
import os
import random
import time
import uuid
from argparse import Namespace
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles
import nonebot
from nonebot import Bot, logger
from nonebot.adapters import Event
from nonebot_plugin_alconna import UniMessage

from ..config import config, BACKEND_URL_LIST
from ..constants import REFLEX_DICT, MAX_SEED
from ..exceptions import (
    ComfyuiNotAvaInCurrentGroup,
    InputFileNotFoundError,
    TextContentNotSafeError,
    ComfyUIPluginError
)
from ..services.comfy_client import comfy_client
from ..services.workflow_engine import workflow_engine
from ..services.lora_engine import lora_engine
from ..services.audit import audit_image, text_audit
from ..services.rate_limiter import rate_limiter
from ..utils.media import (
    send_msg_and_revoke,
    send_msg_to_private,
    get_qr,
    extract_images_from_event
)


class TaskRecordManager:
    """全局任务状态与用户任务映射追踪"""
    all_task_ids: set[str] = set()
    user_tasks: dict[str, dict[str, dict[str, Any]]] = {}

    @classmethod
    def record_task(cls, user_id: str, task_id: str, backend_index: int, wf: str, status: str = "pending") -> None:
        if user_id not in cls.user_tasks:
            cls.user_tasks[user_id] = {}
        cls.user_tasks[user_id][task_id] = {
            "backend_index": backend_index,
            "work_flow": wf,
            "status": status,
            "time": time.time()
        }
        cls.all_task_ids.add(task_id)

    @classmethod
    def update_status(cls, task_id: str, status: str) -> None:
        for u_tasks in cls.user_tasks.values():
            if task_id in u_tasks:
                u_tasks[task_id]["status"] = status

    @classmethod
    def get_user_tasks(cls, user_id: str) -> dict[str, dict[str, Any]]:
        return cls.user_tasks.get(user_id, {})


class GenerationContext:
    """生图任务上下文，管理单次生图生命周期与结果收集"""

    def __init__(self, bot: Bot, event: Event, args: Namespace, **kwargs: Any) -> None:
        self.bot = bot
        self.event = event
        self.args = args
        self.user_id = str(event.get_user_id())

        # 群聊 ID
        self.group_id = str(getattr(event, "group_id", ""))

        # 检查群白名单/禁用规则
        enable_cfg = config.comfyui_group_config.get('enable_in_group', {})
        if self.group_id and self.group_id in enable_cfg:
            if int(enable_cfg[self.group_id]) == 0:
                raise ComfyuiNotAvaInCurrentGroup("本群已禁用 ComfyUI 生图插件")

        # 默认参数计算
        defaults = config.comfyui_default_value
        self.work_flows: str = getattr(args, "work_flows", None) or config.comfyui_default_workflows
        if self.work_flows == config.comfyui_default_workflows and config.comfyui_random_wf:
            self.work_flows = random.choice(config.comfyui_random_wf_list)

        self.override: bool = getattr(args, "override", False) or defaults.get("override", False)
        self.override_ng: bool = getattr(args, "override_ng", False) or defaults.get("override_ng", False)

        raw_prompt = getattr(args, "prompt", [])
        if isinstance(raw_prompt, list):
            raw_prompt_str = " ".join(raw_prompt)
        else:
            raw_prompt_str = str(raw_prompt)

        raw_neg = getattr(args, "negative_prompt", [])
        if isinstance(raw_neg, list):
            raw_neg_str = " ".join(raw_neg)
        else:
            raw_neg_str = str(raw_neg or "")

        preset_p = defaults.get("preset_prompt", "")
        preset_np = defaults.get("preset_negative_prompt", "")

        self.prompt = (f"{preset_p}, {raw_prompt_str}" if (preset_p and not self.override) else raw_prompt_str).strip(", ")
        self.negative_prompt = (f"{preset_np}, {raw_neg_str}" if (preset_np and not self.override_ng) else raw_neg_str).strip(", ")

        self.shape: str | None = getattr(args, "shape", None) or defaults.get("shape")
        self.accept_ratio: str | None = getattr(args, "accept_ratio", None) or defaults.get("accept_ratio")
        self.width, self.height = workflow_engine.calculate_dimensions(
            shape=self.shape,
            accept_ratio=self.accept_ratio,
            width=getattr(args, "width", None),
            height=getattr(args, "height", None)
        )

        self.seed: int = getattr(args, "seed", None) or random.randint(0, MAX_SEED)
        self.steps: int = getattr(args, "steps", None) or defaults.get("steps", 28)
        self.cfg_scale: float = getattr(args, "cfg_scale", None) or defaults.get("cfg_scale", 7.0)
        self.denoise_strength: float = getattr(args, "denoise_strength", None) or defaults.get("denoise_strength", 1.0)

        # 采样器与调度器映射
        sp = getattr(args, "sampler", None) or defaults.get("sampler", "dpmpp_2m")
        self.sampler = REFLEX_DICT['sampler'].get(sp, sp)
        sch = getattr(args, "scheduler", None) or defaults.get("scheduler", "karras")
        self.scheduler = REFLEX_DICT['scheduler'].get(sch, sch)

        self.batch_size: int = getattr(args, "batch_size", None) or defaults.get("batch_size", 1)
        self.batch_count: int = getattr(args, "batch_count", None) or defaults.get("batch_count", 1)
        self.model: str = getattr(args, "model", None) or config.comfyui_model or defaults.get("model", "")
        self.forward: bool = getattr(args, "forward", False) or defaults.get("forward", False)
        self.concurrency: bool = getattr(args, "concurrency", False) or defaults.get("concurrency", False)
        self.silent: bool = getattr(args, "silent", False) or config.comfyui_silent
        self.quiet: bool = config.comfyui_quiet
        self.notice: bool = getattr(args, "notice", False) or defaults.get("notice", False)
        self.pure: bool = getattr(args, "pure", False) or defaults.get("pure", False)
        self.no_trans: bool = getattr(args, "no_trans", False)
        self.selected_backend: str | None = getattr(args, "backend", None)

        self.init_images: list[bytes] = []
        self.loras: list[tuple[str, float]] = []

        # 耗时统计
        self.timings = {"pre_process": 0.0, "request": 0.0, "audit": 0.0, "get_resp": 0.0}
        self.media_results: list[dict[str, Any]] = []
        self.text_pure_info: str = ""
        self.audit_info_msg: str = ""

    def apply_user_limitations(self) -> None:
        """非超级用户限制最大生图尺寸与步数"""
        if self.user_id in config.comfyui_superusers:
            return
        max_dict = config.comfyui_max_dict
        if "batch_size" in max_dict:
            self.batch_size = min(self.batch_size, max_dict["batch_size"])
        if "batch_count" in max_dict:
            self.batch_count = min(self.batch_count, max_dict["batch_count"])
        if "width" in max_dict:
            self.width = min(self.width, max_dict["width"])
        if "height" in max_dict:
            self.height = min(self.height, max_dict["height"])
        if "steps" in max_dict:
            self.steps = min(self.steps, max_dict["steps"])

    async def preprocess_prompts(self) -> None:
        """提示词解析、安全审核与翻译"""
        # 提取 LoRA 标签
        self.prompt, self.loras = lora_engine.extract_loras_from_prompt(self.prompt)

        # 文本安全审查
        text_audit_cfg = config.comfyui_group_config.get("reject_nsfw_prompts", {})
        audit_lvl = text_audit_cfg.get(self.group_id, 1 if config.comfyui_text_audit else 0)

        if audit_lvl == 1:
            res = await text_audit(self.prompt)
            if "yes" in res:
                raise TextContentNotSafeError("文字提示词存在违规内容，已拦截")
        elif audit_lvl == 2:
            prompt_fix = "接下来请你对一些聊天内容进行审核,如果内容出现色情,血腥内容,请你将其去掉,只需要回复调整过的内容,不要回复其他内容"
            res = await text_audit(self.prompt, custom_prompt=prompt_fix)
            self.text_pure_info = f"由于群规则设置，提示词已被自动调整为: {res}"
            self.prompt = res

    async def execute(self) -> None:
        """核心生图执行流水线"""
        t0 = time.time()
        self.apply_user_limitations()
        await self.preprocess_prompts()

        # 加载工作流定义
        api_json, reflex_json = await workflow_engine.load_workflow_files(self.work_flows)
        workflow_engine.validate_permissions(reflex_json, self.user_id, self.group_id)

        # 检查是否需要输入图片
        if reflex_json.get("load_image") and not self.init_images:
            raise InputFileNotFoundError("当前工作流需要提供输入图片！")

        self.timings["pre_process"] = time.time() - t0

        # 选择后端
        backend_url, backend_idx, _ = await comfy_client.select_backend(self.selected_backend)
        if not self.silent and not self.quiet:
            await send_msg_and_revoke(
                f"已选择工作流: {self.work_flows} (后端 [{backend_idx}])\n正在生成中，请稍候...",
                reply_to=True,
                delay=15
            )

        # 匹配可用 LoRA
        if config.comfyui_auto_lora and self.loras:
            self.loras = await lora_engine.match_available_loras(backend_url, self.loras)

        # 准备图片上传
        uploaded_images = []
        for img_bytes in self.init_images:
            img_id = uuid.uuid4().hex
            resp = await comfy_client.upload_image(backend_url, img_bytes, img_id)
            uploaded_images.append(resp)

        # 构建任务分发
        async def _run_single_task(current_seed: int) -> dict[str, Any]:
            client_id = uuid.uuid4().hex
            run_params = {
                "prompt": self.prompt,
                "negative_prompt": self.negative_prompt,
                "width": self.width,
                "height": self.height,
                "seed": current_seed,
                "steps": self.steps,
                "cfg_scale": self.cfg_scale,
                "denoise_strength": self.denoise_strength,
                "sampler": self.sampler,
                "scheduler": self.scheduler,
                "batch_size": self.batch_size,
                "model": self.model,
                "override": self.override,
                "override_ng": self.override_ng,
                "args": self.args,
                "loras": self.loras
            }

            final_api_json = workflow_engine.apply_reflex(
                raw_api_json=api_json,
                reflex_json=reflex_json,
                params=run_params,
                init_images=uploaded_images,
                backend_index=backend_idx
            )

            task_id = await comfy_client.post_prompt(backend_url, final_api_json, client_id)
            TaskRecordManager.record_task(self.user_id, task_id, backend_idx, self.work_flows, "running")

            # 监听执行进度
            await comfy_client.track_task(backend_url, task_id, client_id)
            TaskRecordManager.update_status(task_id, "finish")

            if self.notice:
                await send_msg_to_private(self.bot, self.user_id, f"您的生图任务已完成 (ID: {task_id})", is_image=False)

            # 获取输出
            hist = await comfy_client.get_history(backend_url, task_id)
            outputs = hist.get(task_id, {}).get("outputs", {})
            return {"task_id": task_id, "backend_url": backend_url, "backend_index": backend_idx, "outputs": outputs}

        t_req_start = time.time()
        tasks = []
        for i in range(self.batch_count):
            tasks.append(_run_single_task(self.seed + i))

        if self.concurrency:
            results = await asyncio.gather(*tasks)
        else:
            results = []
            for t in tasks:
                results.append(await t)
        self.timings["request"] = time.time() - t_req_start

        # 下载媒体资源并审核
        t_download_start = time.time()
        await self._collect_media_and_audit(results, reflex_json)
        self.timings["get_resp"] = time.time() - t_download_start

    async def _collect_media_and_audit(self, results: list[dict[str, Any]], reflex_json: dict[str, Any]) -> None:
        """收集 ComfyUI 输出的媒体文件并进行安全审核与保存"""
        output_node = reflex_json.get('output')
        media_type = reflex_json.get('media', 'image')
        if isinstance(output_node, (int, str)):
            output_node = {media_type: [str(output_node)]}
        elif not isinstance(output_node, dict):
            output_node = {"image": []}

        for item in results:
            task_id = item["task_id"]
            backend_url = item["backend_url"]
            outputs = item["outputs"]
            backend_idx = item["backend_index"]

            images: list[bytes] = []
            videos: list[bytes] = []
            audios: list[bytes] = []
            texts: list[str] = []

            for m_type, node_list in output_node.items():
                for node_id in node_list:
                    node_out = outputs.get(str(node_id), {})
                    if m_type == "image":
                        for img_meta in node_out.get("images", []):
                            fn = img_meta["filename"]
                            sub = img_meta.get("subfolder", "")
                            t = img_meta.get("type", "")
                            url = f"{backend_url}/view?filename={fn}&subfolder={sub}&type={t}"
                            b = await comfy_client.request("GET", url, as_json=False)
                            images.append(b)
                    elif m_type == "video":
                        for v_meta in node_out.get("gifs", []):
                            fn = v_meta["filename"]
                            sub = v_meta.get("subfolder", "")
                            url = f"{backend_url}/view?filename={fn}&subfolder={sub}"
                            b = await comfy_client.request("GET", url, as_json=False)
                            videos.append(b)
                    elif m_type == "audio":
                        for a_meta in node_out.get("audio", []):
                            fn = a_meta["filename"]
                            sub = a_meta.get("subfolder", "")
                            url = f"{backend_url}/view?filename={fn}&subfolder={sub}"
                            b = await comfy_client.request("GET", url, as_json=False)
                            audios.append(b)
                    elif m_type == "text":
                        for txt in node_out.get("text", []):
                            texts.append(txt)

            # 保存本地备份
            if config.comfyui_save_image and images:
                self._save_images_locally(images, task_id)

            # 图像审核
            t_audit_start = time.time()
            safe_images: list[bytes] = []
            nsfw_images: list[bytes] = []

            for img_b in images:
                audit_res = await audit_image(img_b, self.group_id)
                self.audit_info_msg = audit_res.get("message", "")
                if audit_res.get("is_nsfw"):
                    nsfw_images.append(img_b)
                else:
                    safe_images.append(img_b)
            self.timings["audit"] += time.time() - t_audit_start

            self.media_results.append({
                "task_id": task_id,
                "backend_index": backend_idx,
                "safe_images": safe_images,
                "nsfw_images": nsfw_images,
                "videos": videos,
                "audios": audios,
                "texts": texts
            })

    def _save_images_locally(self, images: list[bytes], task_id: str) -> None:
        today_str = datetime.now().strftime("%Y-%m-%d")
        out_dir = Path("data/comfyui/output/image") / today_str / self.user_id
        out_dir.mkdir(parents=True, exist_ok=True)
        for idx, img_b in enumerate(images):
            h = hashlib.md5(img_b).hexdigest()
            target = out_dir / f"{h}_{idx}.png"
            with open(target, "wb") as f:
                f.write(img_b)

    async def send_responses(self) -> None:
        """根据配置、群设置及审核结果组装并发送消息"""
        is_pure = self.pure or bool(config.comfyui_group_config.get("pure", {}).get(self.group_id))

        time_info = (
            f"各步骤耗时: 预处理: {self.timings['pre_process']:.2f}s; "
            f"生成请求: {self.timings['request']:.2f}s; "
            f"下载: {self.timings['get_resp']:.2f}s; "
            f"审核: {self.timings['audit']:.2f}s"
        )

        for res in self.media_results:
            task_id = res["task_id"]
            backend_idx = res["backend_index"]
            safe_imgs = res["safe_images"]
            nsfw_imgs = res["nsfw_images"]

            # 处理敏感图片 (保留原有 r18_action 行为)
            for nsfw_b in nsfw_imgs:
                if config.comfyui_r18_action == 1:
                    await send_msg_to_private(self.bot, self.user_id, nsfw_b, is_image=True)
                    await UniMessage.text("⚠️ 生成的图片太涩了，已为您私聊发送！").send(reply_to=True)
                elif config.comfyui_r18_action == 2:
                    qr_b, _ = await get_qr(nsfw_b, self.bot)
                    await UniMessage.image(raw=qr_b).send(reply_to=True)
                elif config.comfyui_r18_action == 3:
                    _, url = await get_qr(nsfw_b, self.bot)
                    await UniMessage.text(f"⚠️ 图片太涩了，访问链接查看: {url}").send(reply_to=True)
                else:
                    await UniMessage.text("⚠️ 图片太涩了，已被过滤拦截！").send(reply_to=True)

            # 处理安全图片
            out_unimsg = UniMessage()
            if not is_pure:
                header = f"{time_info}\n任务ID: {task_id}, 后端索引: {backend_idx}\n"
                if self.audit_info_msg:
                    header += f"审核信息: {self.audit_info_msg}\n"
                if self.text_pure_info:
                    header += f"{self.text_pure_info}\n"
                out_unimsg += header

            for t in res["texts"]:
                out_unimsg += f"{t}\n"

            # 发送方式判断 (普通图片 / 二维码 / URL)
            img_send_mode = config.comfyui_group_config.get("img_send", {}).get(self.group_id, config.comfyui_img_send)
            for img_b in safe_imgs:
                if img_send_mode == 1:
                    out_unimsg += UniMessage.image(raw=img_b)
                elif img_send_mode == 2:
                    qr_b, _ = await get_qr(img_b, self.bot)
                    out_unimsg += UniMessage.image(raw=qr_b)
                elif img_send_mode == 3:
                    _, url = await get_qr(img_b, self.bot)
                    out_unimsg += f"\n图片链接: {url}"

            await out_unimsg.send(reply_to=True)

            # 音视频外发
            for vid_b in res["videos"]:
                await UniMessage.video(raw=vid_b).send()
            for aud_b in res["audios"]:
                await UniMessage.audio(raw=aud_b).send()


from nonebot.params import ShellCommandArgs


async def comfyui_generate_handler(bot: Bot, event: Event, args: Namespace = ShellCommandArgs()) -> None:
    """生图指令主调度流程，集成限流与异常处理"""
    user_id = str(event.get_user_id())
    is_su = user_id in config.comfyui_superusers

    # 1. 冷却检查
    in_cd, remain = rate_limiter.check_cd(user_id, is_su)
    if in_cd:
        await send_msg_and_revoke(f"您冲得太快啦，请休息一下，剩余冷却时间为: {remain}s", reply_to=True, delay=8)
        return

    # 2. 每日调用次数检查
    daily_key = rate_limiter.get_today_key(user_id)
    b_size = getattr(args, "batch_size", 1) or 1
    b_count = getattr(args, "batch_count", 1) or 1
    total_imgs = b_size * b_count
    wf = getattr(args, "work_flows", config.comfyui_default_workflows)

    limit_msg, reached = rate_limiter.check_daily_limit(daily_key, total_imgs, is_su, wf_name=wf)
    if reached:
        await send_msg_and_revoke(f"调用受限: {limit_msg}", reply_to=True, delay=15)
        return

    rate_limiter.update_cd(user_id)

    # 3. 构造并执行
    ctx = GenerationContext(bot, event, args)
    try:
        ctx.init_images = await extract_images_from_event(event, allow_gif=getattr(args, "gif", False))
        await ctx.execute()
        await ctx.send_responses()
    except ComfyUIPluginError as pe:
        rate_limiter.revert_daily(daily_key, total_imgs)
        logger.error(f"ComfyUI 生图失败: {pe}")
        await send_msg_and_revoke(f"生图失败: {pe.message}", reply_to=True, delay=20)
    except Exception as e:
        rate_limiter.revert_daily(daily_key, total_imgs)
        logger.exception("ComfyUI 生图未知异常")
        await send_msg_and_revoke(f"生图发生未知错误: {e}", reply_to=True, delay=20)
