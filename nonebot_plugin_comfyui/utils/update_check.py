from importlib.metadata import version as get_local_version, PackageNotFoundError
from packaging.version import parse as parse_version
from datetime import datetime
from nonebot import logger
from ..services.comfy_client import comfy_client

PACKAGE_NAME: str = "nonebot-plugin-comfyui"


async def get_recent_commits(num_commits: int = 3) -> str:
    url = f"https://api.github.com/repos/DiaoDaiaChan/{PACKAGE_NAME}/commits"
    params = {"per_page": num_commits, "page": 1}
    try:
        commits = await comfy_client.request("GET", url, params=params, timeout=5)
        if not isinstance(commits, list):
            return ""
        details = []
        for c in commits:
            c_data = c.get("commit", {})
            sha = c.get("sha", "")[:7]
            msg = c_data.get("message", "").strip()
            date_str = c_data.get("author", {}).get("date", "")
            if date_str:
                try:
                    date_str = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass
            details.append(f"🔹 {msg}\n   - 哈希: {sha}\n   - 时间: {date_str}\n")
        return "\n".join(details)
    except Exception as e:
        logger.debug(f"获取最新 Commit 失败: {e}")
        return ""


async def check_package_update() -> tuple[str, bool]:
    """检查 PyPI 版本更新，安全处理本地未安装场景"""
    try:
        local_ver_str = get_local_version(PACKAGE_NAME)
        local_version = parse_version(local_ver_str)
    except PackageNotFoundError:
        return "", False

    try:
        pypi_data = await comfy_client.request(
            "GET",
            f"https://pypi.org/pypi/{PACKAGE_NAME}/json",
            headers={"User-Agent": "Python-Package-Version-Checker"},
            timeout=3
        )
        if not isinstance(pypi_data, dict) or "info" not in pypi_data:
            return "", False
        latest_version = parse_version(pypi_data["info"]["version"])
    except Exception:
        return "", False

    if local_version < latest_version:
        repo_url = f"https://github.com/DiaoDaiaChan/{PACKAGE_NAME}"
        commit_msg = await get_recent_commits()
        msg = (
            f"🎉 {PACKAGE_NAME} 发现新版本！\n"
            f"当前版本：{local_version}\n"
            f"最新版本：{latest_version}\n"
            f"更新命令：pip install --upgrade {PACKAGE_NAME}\n"
            f"{repo_url}#更新日志\n"
            f"{commit_msg}"
        )
        return msg, True

    return "", False
