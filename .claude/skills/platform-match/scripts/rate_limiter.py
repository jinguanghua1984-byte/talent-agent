#!/usr/bin/env python3
"""rate_limiter.py — 令牌桶限流 + 熔断机制

三层频率控制:
1. 硬性底线（不可配置）
2. 弹性控制（可配置）
3. 异常熔断（自动触发）

用法:
    python rate_limiter.py status --platform maimai
    python rate_limiter.py tick --platform maimai
    python rate_limiter.py reset
"""

import argparse
import json
import logging
import os
import random
import sys
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

SESSION_DIR = os.path.join(os.getcwd(), "data", "session")
STATE_FILE = os.path.join(SESSION_DIR, "rate-limit-state.json")


@dataclass(frozen=True)
class HardLimits:
    """硬性底线（不可配置）。"""
    search_interval_min: float = 3.0
    search_interval_max: float = 8.0
    page_interval_min: float = 2.0
    page_interval_max: float = 5.0
    continuous_op_minutes: int = 30
    continuous_pause_min: float = 60.0
    continuous_pause_max: float = 120.0


@dataclass(frozen=True)
class HeadlessLimits:
    """降级模式限流参数（更保守）。"""
    search_interval_min: float = 8.0
    search_interval_max: float = 15.0
    batch_max: int = 15
    daily_max: int = 80


@dataclass(frozen=True)
class ElasticConfig:
    """弹性控制（可配置）。"""
    batch_max: int = 30
    batch_pause_min: float = 300.0
    batch_pause_max: float = 600.0
    daily_max: int = 200


DEFAULT_LIMITS = {
    "maimai": ElasticConfig(),
}


@dataclass
class CircuitState:
    """熔断状态。"""
    is_open: bool = False
    trigger_reason: str = ""
    triggered_at: float = 0.0
    consecutive_failures: int = 0


@dataclass
class PlatformState:
    """单平台状态。"""
    last_search_at: float = 0.0
    last_page_at: float = 0.0
    continuous_op_count: int = 0
    continuous_op_start: float = 0.0
    batch_count: int = 0
    daily_count: int = 0
    daily_date: str = ""
    circuit: CircuitState = field(default_factory=CircuitState)


# ---------------------------------------------------------------------------
# 文件锁（跨平台，上下文管理器）
# ---------------------------------------------------------------------------

from contextlib import contextmanager


@contextmanager
def _file_lock(filepath: str):
    """跨平台文件锁上下文管理器。"""
    lock_path = filepath + ".lock"
    lock_fd = None
    try:
        lock_fd = open(lock_path, "w")
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    except (IOError, OSError):
        logger.warning("文件锁获取失败，继续执行（并发写入可能导致状态不一致）")
        yield  # 锁获取失败，静默继续
    finally:
        if lock_fd:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    msvcrt.locking(lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                lock_fd.close()
            except Exception:
                logger.warning("释放文件锁时出错", exc_info=True)
                try:
                    lock_fd.close()
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# 状态持久化
# ---------------------------------------------------------------------------

def _ensure_session_dir() -> None:
    os.makedirs(SESSION_DIR, exist_ok=True)


def _load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("限流状态文件损坏，已重置: %s", e)
        return {}


def _save_state(state: dict) -> None:
    _ensure_session_dir()
    tmp_path = STATE_FILE + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, STATE_FILE)
    except OSError as e:
        logger.error("限流状态保存失败: %s", e)


def _get_platform_state(platform: str, headless: bool = False) -> PlatformState:
    state = _load_state()
    key = f"{platform}_headless" if headless else platform
    raw = state.get(key, {})
    return PlatformState(
        last_search_at=raw.get("last_search_at", 0.0),
        last_page_at=raw.get("last_page_at", 0.0),
        continuous_op_count=raw.get("continuous_op_count", 0),
        continuous_op_start=raw.get("continuous_op_start", 0.0),
        batch_count=raw.get("batch_count", 0),
        daily_count=raw.get("daily_count", 0),
        daily_date=raw.get("daily_date", ""),
        circuit=CircuitState(
            is_open=raw.get("circuit", {}).get("is_open", False),
            trigger_reason=raw.get("circuit", {}).get("trigger_reason", ""),
            triggered_at=raw.get("circuit", {}).get("triggered_at", 0.0),
            consecutive_failures=raw.get("circuit", {}).get("consecutive_failures", 0),
        ),
    )


def _save_platform_state(platform: str, ps: PlatformState, headless: bool = False) -> None:
    state = _load_state()
    key = f"{platform}_headless" if headless else platform
    state[key] = {
        "last_search_at": ps.last_search_at,
        "last_page_at": ps.last_page_at,
        "continuous_op_count": ps.continuous_op_count,
        "continuous_op_start": ps.continuous_op_start,
        "batch_count": ps.batch_count,
        "daily_count": ps.daily_count,
        "daily_date": ps.daily_date,
        "circuit": {
            "is_open": ps.circuit.is_open,
            "trigger_reason": ps.circuit.trigger_reason,
            "triggered_at": ps.circuit.triggered_at,
            "consecutive_failures": ps.circuit.consecutive_failures,
        },
    }
    _save_state(state)


# ---------------------------------------------------------------------------
# 限流逻辑
# ---------------------------------------------------------------------------

def check_search(platform: str, headless: bool = False) -> dict:
    """检查是否可以执行搜索，返回等待时间。"""
    ps = _get_platform_state(platform, headless)
    hard = HardLimits()
    elastic = DEFAULT_LIMITS.get(platform, ElasticConfig())

    hl = HeadlessLimits()

    # 检查熔断
    if ps.circuit.is_open:
        elapsed = time.time() - ps.circuit.triggered_at
        cooldown = 1800  # 30 分钟
        if elapsed < cooldown:
            return {
                "allowed": False,
                "reason": "circuit_break",
                "wait_seconds": int(cooldown - elapsed),
                "trigger_reason": ps.circuit.trigger_reason,
            }
        else:
            ps = PlatformState(
                last_search_at=ps.last_search_at,
                last_page_at=ps.last_page_at,
                continuous_op_count=0,
                continuous_op_start=time.time(),
                batch_count=ps.batch_count,
                daily_count=ps.daily_count,
                daily_date=ps.daily_date,
            )

    now = time.time()

    # 检查搜索间隔
    min_interval = hl.search_interval_min if headless else hard.search_interval_min
    max_interval = hl.search_interval_max if headless else hard.search_interval_max
    if ps.last_search_at > 0:
        elapsed_since_search = now - ps.last_search_at
        if elapsed_since_search < min_interval:
            return {
                "allowed": False,
                "reason": "rate_limit",
                "wait_seconds": int(min_interval - elapsed_since_search),
            }

    # 检查连续操作上限
    if ps.continuous_op_count >= 10:
        elapsed_continuous = now - ps.continuous_op_start
        if elapsed_continuous <= hard.continuous_op_minutes * 60:
            pause = random.uniform(hard.continuous_pause_min, hard.continuous_pause_max)
            return {
                "allowed": False,
                "reason": "continuous_pause",
                "wait_seconds": int(pause),
            }

    # 检查批次上限
    batch_max = hl.batch_max if headless else elastic.batch_max
    if ps.batch_count >= batch_max:
        pause = random.uniform(elastic.batch_pause_min, elastic.batch_pause_max)
        return {
            "allowed": False,
            "reason": "batch_limit",
            "wait_seconds": int(pause),
        }

    # 检查每日上限
    daily_max = hl.daily_max if headless else elastic.daily_max
    today = time.strftime("%Y-%m-%d")
    if ps.daily_date == today and ps.daily_count >= daily_max:
        return {
            "allowed": False,
            "reason": "daily_limit",
            "wait_seconds": 86400,
        }

    # 计算随机延迟
    if ps.last_search_at > 0:
        delay = random.uniform(min_interval, max_interval)
    else:
        delay = 0

    return {"allowed": True, "delay_seconds": delay}


def record_search(platform: str, headless: bool = False) -> None:
    """记录一次搜索操作。"""
    with _file_lock(STATE_FILE):
        ps = _get_platform_state(platform, headless)
        now = time.time()
        today = time.strftime("%Y-%m-%d")

        ps = PlatformState(
            last_search_at=now,
            last_page_at=ps.last_page_at,
            continuous_op_count=ps.continuous_op_count + 1,
            continuous_op_start=ps.continuous_op_start if ps.continuous_op_start > 0 else now,
            batch_count=ps.batch_count + 1,
            daily_count=ps.daily_count + 1 if ps.daily_date == today else 1,
            daily_date=today,
            circuit=CircuitState(),
        )
        _save_platform_state(platform, ps, headless)


def record_page(platform: str, headless: bool = False) -> None:
    """记录一次翻页操作。"""
    with _file_lock(STATE_FILE):
        ps = _get_platform_state(platform, headless)
        ps = PlatformState(
            last_search_at=ps.last_search_at,
            last_page_at=time.time(),
            continuous_op_count=ps.continuous_op_count + 1,
            continuous_op_start=ps.continuous_op_start,
            batch_count=ps.batch_count,
            daily_count=ps.daily_count,
            daily_date=ps.daily_date,
            circuit=ps.circuit,
        )
        _save_platform_state(platform, ps, headless)


def trigger_circuit_break(platform: str, reason: str, headless: bool = False) -> None:
    """触发熔断。"""
    with _file_lock(STATE_FILE):
        ps = _get_platform_state(platform, headless)
        ps = PlatformState(
            last_search_at=ps.last_search_at,
            last_page_at=ps.last_page_at,
            continuous_op_count=ps.continuous_op_count,
            continuous_op_start=ps.continuous_op_start,
            batch_count=ps.batch_count,
            daily_count=ps.daily_count,
            daily_date=ps.daily_date,
            circuit=CircuitState(
                is_open=True,
                trigger_reason=reason,
                triggered_at=time.time(),
                consecutive_failures=ps.circuit.consecutive_failures + 1,
            ),
        )
        _save_platform_state(platform, ps, headless)


# ---------------------------------------------------------------------------
# CLI 命令
# ---------------------------------------------------------------------------

def cmd_status(args):
    ps = _get_platform_state(args.platform, args.headless)
    result = {
        "platform": args.platform,
        "headless": args.headless,
        "last_search_at": ps.last_search_at,
        "batch_count": ps.batch_count,
        "daily_count": ps.daily_count,
        "daily_date": ps.daily_date,
        "circuit_open": ps.circuit.is_open,
    }
    if ps.circuit.is_open:
        result["circuit_reason"] = ps.circuit.trigger_reason
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_tick(args):
    check = check_search(args.platform, args.headless)
    print(json.dumps(check, ensure_ascii=False, indent=2))
    return 0


def cmd_reset(args):
    with _file_lock(STATE_FILE):
        _save_state({})
        print(json.dumps({"status": "ok", "message": "已重置所有限流状态"}, ensure_ascii=False, indent=2))
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="限流管理 CLI")
    subparsers = parser.add_subparsers(dest="command")

    status_p = subparsers.add_parser("status", help="查看限流状态")
    status_p.add_argument("--platform", required=True, help="平台名称")
    status_p.add_argument("--headless", action="store_true")

    tick_p = subparsers.add_parser("tick", help="检查是否可以执行操作")
    tick_p.add_argument("--platform", required=True, help="平台名称")
    tick_p.add_argument("--headless", action="store_true")

    subparsers.add_parser("reset", help="重置所有限流状态")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    handlers = {
        "status": cmd_status,
        "tick": cmd_tick,
        "reset": cmd_reset,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
