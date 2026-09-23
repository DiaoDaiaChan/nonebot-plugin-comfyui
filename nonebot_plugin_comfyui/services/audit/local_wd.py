import asyncio
from typing import Any
from pathlib import Path
from io import BytesIO
from PIL import Image
from nonebot import logger
from ...config import config
from .base import BaseAuditor, prepare_audit_image


class LocalWDAuditor(BaseAuditor):
    """本地 WaifuDiffusion ONNX 审核器（延迟加载，避免启动阻塞）"""

    def __init__(self) -> None:
        self._interrogator = None
        self._load_lock = asyncio.Lock()

    def _ensure_loaded(self) -> Any:
        if self._interrogator is not None:
            return self._interrogator

        try:
            from onnxruntime import InferenceSession
            import pandas as pd
            import numpy as np
            from huggingface_hub import hf_hub_download
        except ImportError as e:
            logger.error(
                f"本地 WD14 审核依赖缺失: {e}。\n"
                f"请手动安装: pip install onnxruntime pandas numpy huggingface_hub"
            )
            raise e

        wd_cfg = config.comfyui_wd_model
        logger.info(f"正在加载本地 WD14 模型: {wd_cfg.get('repo_id')}")

        model_path = hf_hub_download(
            repo_id=wd_cfg['repo_id'],
            revision=wd_cfg.get('revision', 'v2.0'),
            filename=wd_cfg.get('model_path', 'model.onnx')
        )
        tags_path = hf_hub_download(
            repo_id=wd_cfg['repo_id'],
            revision=wd_cfg.get('revision', 'v2.0'),
            filename=wd_cfg.get('tags_path', 'selected_tags.csv')
        )

        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
        if not config.comfyui_audit_gpu:
            providers = ['CPUExecutionProvider']

        session = InferenceSession(str(model_path), providers=providers)
        tags_df = pd.read_csv(tags_path)

        class WDWrapper:
            def __init__(self, sess, tags):
                self.sess = sess
                self.tags = tags

            def run_infer(self, pil_img: Image.Image) -> tuple[dict[str, float], dict[str, float]]:
                _, height, _, _ = self.sess.get_inputs()[0].shape
                img = pil_img.convert('RGBA')
                new_img = Image.new('RGBA', img.size, 'WHITE')
                new_img.paste(img, mask=img)
                img = new_img.convert('RGB')
                arr = np.asarray(img)[:, :, ::-1]

                # Make square and resize
                old_size = arr.shape[:2]
                ratio = float(height) / max(old_size)
                new_size = tuple([int(x * ratio) for x in old_size])
                im_pil = Image.fromarray(arr).resize(new_size, Image.LANCZOS)
                canvas = Image.new("RGB", (height, height))
                canvas.paste(im_pil, ((height - new_size[0]) // 2, (height - new_size[1]) // 2))

                in_arr = np.array(canvas).astype(np.float32)
                in_arr = np.expand_dims(in_arr, 0)

                in_name = self.sess.get_inputs()[0].name
                out_name = self.sess.get_outputs()[0].name
                confidents = self.sess.run([out_name], {in_name: in_arr})[0]

                tags_col = self.tags[['name']].copy()
                tags_col['confidents'] = confidents[0]

                ratings = dict(tags_col[:4].values)
                tags_dict = dict(tags_col[4:].values)
                return ratings, tags_dict

        self._interrogator = WDWrapper(session, tags_df)
        logger.info("本地 WD14 模型加载就绪")
        return self._interrogator

    async def audit(self, image_bytes: bytes, group_id: str = "") -> dict[str, Any]:
        audit_info = {
            "is_nsfw": False,
            "message": "",
            "tags": {}
        }

        try:
            async with self._load_lock:
                interrogator = await asyncio.to_thread(self._ensure_loaded)
        except Exception as e:
            audit_info["message"] = f"本地 WD14 加载失败: {e}"
            return audit_info

        b64, pil_img = prepare_audit_image(image_bytes)
        ratings, _ = await asyncio.to_thread(interrogator.run_infer, pil_img)

        # 判定等级
        audit_level = config.comfyui_audit_level
        group_cfg = config.comfyui_group_config.get("audit_level_group", {})
        if group_id and group_id in group_cfg:
            try:
                audit_level = int(group_cfg[group_id])
            except ValueError:
                pass

        sorted_ratings = sorted(ratings.items(), key=lambda x: x[1], reverse=True)
        top_category, top_score = sorted_ratings[0]

        is_nsfw = False
        if audit_level == 1:
            is_nsfw = (top_category == "explicit")
        elif audit_level == 2:
            is_nsfw = top_category in ("questionable", "explicit")
        elif audit_level == 3:
            is_nsfw = top_category in ("questionable", "explicit", "sensitive")
        elif audit_level >= 100:
            is_nsfw = True
        elif audit_level == 0:
            is_nsfw = False

        audit_info["tags"] = ratings
        audit_info["message"] = f"WD14 本地审核判定: {top_category} ({top_score * 100:.1f}%)"
        audit_info["is_nsfw"] = is_nsfw
        return audit_info


local_wd_auditor = LocalWDAuditor()
