from importlib.metadata import version as get_local_version, PackageNotFoundError
from packaging.version import parse as parse_version
from datetime import datetime
from ..backend.utils import http_request


package_name = "nonebot-plugin-comfyui"


async def get_recent_commit_messages(num_commits=3):
    url = f"https://api.github.com/repos/DiaoDaiaChan/nonebot-plugin-comfyui/commits"
    params = {
        "per_page": num_commits,
        "page": 1,
    }
    try:
        commits = await http_request("GET", target_url=url, params=params)
        commit_details = []
        for commit in commits:
            commit_data = commit["commit"]
            commit_hash = commit["sha"][:7]
            commit_message = commit_data["message"].strip()
            commit_time = commit_data["author"]["date"]

            commit_time = datetime.strptime(commit_time, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S")

            commit_details.append(
                f"🔹 {commit_message}\n"
                f"   - 哈希: {commit_hash}\n"
                f"   - 时间: {commit_time}\n"
            )

        return "\n".join(commit_details)
    except:
        return ""

#
# def auto_update_package(auto_confirm: bool = False) -> Tuple[bool, str]:
#
#     check_result = check_package_update(package_name)
#
#     if not check_result or "发现新版本" not in check_result:
#         return (False, check_result if check_result else "无需更新")
#
#     print("\n" + check_result)
#
#     if not auto_confirm:
#         try:
#             choice = input("\n是否要立即更新？[y/N] ").strip().lower()
#             if choice not in ['y', 'yes']:
#                 return (False, "用户取消更新")
#         except KeyboardInterrupt:
#             return (False, "更新已中止")
#
#     try:
#         result = subprocess.run(
#             [sys.executable, "-m", "pip", "install", "--upgrade", package_name],
#             check=True,
#             capture_output=True,
#             text=True
#         )
#
#         new_version = parse_version(get_local_version(package_name))
#         return (True, f"✅ 成功更新到版本 {new_version}\n输出日志：{result.stdout}")
#
#     except subprocess.CalledProcessError as e:
#         error_msg = f"更新失败：{e.stderr}" if e.stderr else "未知错误"
#         return (False, f"⛔ {error_msg}")
#     except PackageNotFoundError:
#         return (False, "⚠️ 更新后包仍然未安装")
#     except Exception as e:
#         return (False, f"⛔ 意外错误：{str(e)}")


async def check_package_update():
    local_version = parse_version(get_local_version(package_name))

    try:
        pypi_data = await http_request(
            "GET",
            target_url=f"https://pypi.org/pypi/{package_name}/json",
            headers={"User-Agent": "Python-Package-Version-Checker"},
            timeout=3
        )
        latest_version = parse_version(pypi_data["info"]["version"])
    except Exception as e:
        return f"连接PyPI失败：{str(e)}", False

    if local_version < latest_version:
        repo_url = "https://github.com/DiaoDaiaChan/nonebot-plugin-comfyui"
        commit_msg = await get_recent_commit_messages()
        return (
            f"🎉 nonebot_plugin_comfyui发现新版本！\n"
            f"当前版本：{local_version}\n"
            f"最新版本：{latest_version}\n"
            f"更新命令：pip install --upgrade {package_name}\n"
            f"{repo_url}#更新日志\n"
            f"{commit_msg}"
        ), True
    return '', False

