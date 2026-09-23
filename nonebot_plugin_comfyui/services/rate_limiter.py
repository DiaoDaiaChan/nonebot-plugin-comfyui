import datetime
import time
from typing import Any
from ..config import config


class RateLimiter:
    """限流与冷却管理器，线程/协程安全的数据管理"""

    def __init__(self) -> None:
        self.cd_records: dict[str, float] = {}
        self.daily_records: dict[str, int] = {}
        self.workflow_daily_records: dict[str, dict[str, int]] = {}

    def get_today_key(self, user_id: str) -> str:
        today_date = datetime.datetime.now().strftime('%Y-%m-%d')
        return f"{user_id}:{today_date}"

    def check_cd(self, user_id: str, is_superuser: bool = False) -> tuple[bool, int]:
        """检查用户冷却状态。返回 (是否在CD中, 剩余CD秒数)"""
        if is_superuser or config.comfyui_cd <= 0:
            return False, 0

        now = time.time()
        last_time = self.cd_records.get(user_id, 0.0)
        delta = now - last_time

        if delta < config.comfyui_cd:
            remaining = int(config.comfyui_cd - delta)
            return True, remaining
        return False, 0

    def update_cd(self, user_id: str) -> None:
        """更新用户的最后请求时间"""
        self.cd_records[user_id] = time.time()

    def check_daily_limit(
        self,
        daily_key: str,
        amount: int,
        is_superuser: bool = False,
        wf_name: str | None = None,
        wf_limit: int | None = None
    ) -> tuple[str, bool]:
        """
        检查并累加每日限额。
        返回: (提示信息, 是否已达上限)
        """
        max_daily = config.comfyui_day_limit
        if is_superuser:
            return "", False

        current = self.daily_records.get(daily_key, 0)
        new_total = current + amount
        self.daily_records[daily_key] = new_total

        is_seconds = config.comfyui_limit_as_seconds
        unit_str = "秒" if is_seconds else "次"

        if new_total >= max_daily:
            msg = f"今天你的使用量已达上限，最多可以使用 {max_daily} {unit_str}。"
            reached = True
        else:
            remaining = max_daily - new_total
            msg = f"今天已使用 {new_total} {unit_str}，还能使用 {remaining} {unit_str}"
            reached = False

        # 工作流独立限额检查
        if wf_name:
            if daily_key not in self.workflow_daily_records:
                self.workflow_daily_records[daily_key] = {}
            wf_current = self.workflow_daily_records[daily_key].get(wf_name, 0) + amount
            self.workflow_daily_records[daily_key][wf_name] = wf_current
            if wf_limit and wf_current > wf_limit:
                msg = f"已超过该工作流每日调用限制（上限 {wf_limit} 次）"
                reached = True

        return msg, reached

    def revert_daily(self, daily_key: str, amount: int) -> None:
        """任务执行失败时回滚计次"""
        if daily_key in self.daily_records:
            self.daily_records[daily_key] = max(0, self.daily_records[daily_key] - amount)

    def get_workflow_daily_usage(self, daily_key: str, wf_name: str) -> int:
        return self.workflow_daily_records.get(daily_key, {}).get(wf_name, 0)


rate_limiter = RateLimiter()
