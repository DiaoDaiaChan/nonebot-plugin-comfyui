import asyncio
import json
import os
import random
import ssl
import time
from typing import Any
from urllib.parse import urlparse
import aiohttp
from aiohttp import TCPConnector
from nonebot import logger
from tqdm import tqdm

from ..config import config, BACKEND_URL_LIST
from ..exceptions import (
    ComfyuiBackendConnectionError,
    NoAvailableBackendError,
    APIJsonError,
    GetResultError
)


class ComfyClient:
    """ComfyUI 后端通信客户端，负责 HTTP API 请求与 WebSocket 跟踪"""

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()

    async def get_session(self) -> aiohttp.ClientSession:
        async with self._lock:
            if self._session is None or self._session.closed:
                ssl_ctx = ssl.create_default_context()
                ssl_ctx.set_ciphers('DEFAULT')
                ssl_ctx.options |= ssl.OP_NO_SSLv2 | ssl.OP_NO_SSLv3 | ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 | ssl.OP_NO_COMPRESSION
                connector = TCPConnector(ssl=ssl_ctx)
                self._session = aiohttp.ClientSession(
                    connector=connector,
                    proxy=config.comfyui_http_proxy if config.comfyui_http_proxy else None
                )
            return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def request(
        self,
        method: str,
        target_url: str,
        headers: dict | None = None,
        params: dict | None = None,
        data: Any = None,
        json_data: Any = None,
        timeout: int = 5000,
        as_json: bool = True,
        as_text: bool = False,
        proxy: bool = False
    ) -> Any:
        session = await self.get_session()
        custom_proxy = config.comfyui_http_proxy if proxy else None
        try:
            async with session.request(
                method,
                target_url,
                headers=headers,
                params=params,
                data=data,
                json=json_data,
                timeout=aiohttp.ClientTimeout(total=timeout),
                proxy=custom_proxy
            ) as response:
                if as_text:
                    return await response.text()
                if as_json:
                    return await response.json()
                return await response.read()
        except Exception as e:
            raise ComfyuiBackendConnectionError(f"请求后端失败 [{target_url}]: {e}")

    async def is_port_open(self, host: str, port: int, timeout: int | None = None) -> bool:
        t = timeout or config.comfyui_timeout
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=t)
            writer.close()
            await writer.wait_closed()
            return True
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            return False

    async def get_backend_work_status(self, url: str) -> dict[str, Any]:
        parsed = urlparse(url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (80 if parsed.scheme == "http" else 443)

        if not await self.is_port_open(host, port):
            raise ComfyuiBackendConnectionError(f"后端 {url} 端口无法连接")
        return await self.request("GET", f"{url}/prompt", timeout=config.comfyui_timeout)

    async def get_available_backends(self) -> tuple[set[int], dict[str, Any]]:
        backend_dict: dict[str, Any] = {}
        available_indices: set[int] = set()

        tasks = [self.get_backend_work_status(url) for url in BACKEND_URL_LIST]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for idx, (res, url) in enumerate(zip(results, BACKEND_URL_LIST)):
            if isinstance(res, Exception):
                logger.warning(f"后端 [{idx}] {url} 掉线或不可用: {res}")
            else:
                backend_dict[url] = res
                available_indices.add(idx)

        return available_indices, backend_dict

    async def select_backend(self, selected_backend: str | None = None) -> tuple[str, int, dict[str, Any]]:
        """选择最佳或指定后端。返回: (url, index, task_info)"""
        if selected_backend:
            if selected_backend.isdigit():
                idx = int(selected_backend)
                if 0 <= idx < len(BACKEND_URL_LIST):
                    return BACKEND_URL_LIST[idx], idx, {}
            elif selected_backend in BACKEND_URL_LIST:
                return selected_backend, BACKEND_URL_LIST.index(selected_backend), {}
            else:
                # 外部自定义 URL
                return selected_backend, -1, {}

        available_indices, backend_dict = await self.get_available_backends()
        if not available_indices:
            raise NoAvailableBackendError("没有可用的 ComfyUI 后端")

        # 选出队列任务最少的后端
        best_url = None
        min_queue = float("inf")
        best_info = {}

        for url, info in backend_dict.items():
            exec_info = info.get("exec_info", {})
            queue_remaining = exec_info.get("queue_remaining", 0)
            if queue_remaining < min_queue:
                min_queue = queue_remaining
                best_url = url
                best_info = info

        if best_url is None:
            best_url = BACKEND_URL_LIST[random.choice(list(available_indices))]

        idx = BACKEND_URL_LIST.index(best_url)
        return best_url, idx, best_info

    async def post_prompt(self, backend_url: str, prompt_json: dict, client_id: str) -> str:
        payload = {
            "client_id": client_id,
            "prompt": prompt_json
        }
        res = await self.request("POST", f"{backend_url}/prompt", json_data=payload)
        if not isinstance(res, dict) or res.get("error"):
            err_msg = res.get("error") if isinstance(res, dict) else str(res)
            node_errors = res.get("node_errors", "") if isinstance(res, dict) else ""
            raise APIJsonError(f"ComfyUI API 错误: {err_msg}\n节点错误: {node_errors}")
        return res["prompt_id"]

    async def upload_image(self, backend_url: str, image_bytes: bytes, name: str, image_type: str = "input", overwrite: bool = False) -> dict:
        session = await self.get_session()
        data = aiohttp.FormData()
        data.add_field('image', image_bytes, filename=f"{name}.png", content_type='image/png')
        data.add_field('type', image_type)
        data.add_field('overwrite', str(overwrite).lower())

        async with session.post(f"{backend_url}/upload/image", data=data) as resp:
            return json.loads(await resp.read())

    async def track_task(self, backend_url: str, task_id: str, client_id: str, timeout: int = 1800) -> None:
        """通过 WebSocket 监听任务执行进度"""
        session = await self.get_session()
        ws_url = f"{backend_url}/ws?clientId={client_id}"
        progress_bar = None
        start_time = time.time()

        try:
            async with session.ws_connect(ws_url, timeout=30.0) as ws:
                logger.info(f"任务 {task_id} 开始追踪 [Client: {client_id}]")
                async for msg in ws:
                    if time.time() - start_time > timeout:
                        raise TimeoutError(f"任务 {task_id} 等待超时")

                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        msg_type = data.get("type")

                        if msg_type == "progress" and data.get("data", {}).get("prompt_id") == task_id:
                            val = data["data"]["value"]
                            max_val = data["data"]["max"]
                            if progress_bar is None:
                                progress_bar = await asyncio.to_thread(
                                    tqdm, total=max_val,
                                    desc=f"[{backend_url}] Task: {task_id[:8]}",
                                    unit="steps"
                                )
                            delta = val - progress_bar.n
                            if delta > 0:
                                await asyncio.to_thread(progress_bar.update, delta)

                        elif msg_type == "executing":
                            exec_data = data.get("data", {})
                            if exec_data.get("node") is None and exec_data.get("prompt_id") == task_id:
                                logger.info(f"任务 {task_id} 执行完毕！")
                                break

                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error(f"WebSocket 异常中断: {msg.data}")
                        break
        finally:
            if progress_bar is not None:
                await asyncio.to_thread(progress_bar.close)

    async def get_history(self, backend_url: str, task_id: str) -> dict[str, Any]:
        return await self.request("GET", f"{backend_url}/history/{task_id}")

    async def interrupt(self, backend_url: str) -> str:
        return await self.request("POST", f"{backend_url}/interrupt", as_text=True)

    async def delete_queue(self, backend_url: str, task_ids: list[str]) -> str:
        return await self.request("POST", f"{backend_url}/queue", json_data={"delete": task_ids}, as_text=True)

    async def clear_queue(self, backend_url: str) -> str:
        return await self.request("POST", f"{backend_url}/queue", json_data={"clear": True}, as_text=True)

    async def get_loras(self, backend_url: str) -> list[str]:
        resp = await self.request("GET", f"{backend_url}/object_info/LoraLoader")
        try:
            return resp['LoraLoader']['input']['required']['lora_name'][0]
        except Exception:
            return []

    async def get_checkpoints(self, backend_url: str) -> list[str]:
        resp = await self.request("GET", f"{backend_url}/object_info/CheckpointLoaderSimple")
        try:
            return resp['CheckpointLoaderSimple']['input']['required']['ckpt_name'][0]
        except Exception:
            return []


comfy_client = ComfyClient()
