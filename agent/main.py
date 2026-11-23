"""MaaKOG agent 启动入口。

maafw 环境保障：优先用已安装版本（win 发布包已内置 Python + maafw），
缺失时自动 pip 安装锁定版本（mac/linux/android/源码场景）。
"""

import os
import sys

# Embedded Python（win 发布包内置）的 _pth 硬编码了 sys.path，不会把脚本所在
# 目录加进去，导致 import compare_numbers 失败。显式补上脚本目录。
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

# 与发布包 MaaFramework 原生库版本一致（debug/maafw.log 的 Version v5.16.1）
_MAAFW_REQUIRED_VERSION = "5.16.1"
_PIP_INSTALL_TIMEOUT = 300


def _ensure_maafw() -> bool:
    """确保 maafw 已安装且版本可用。返回 True 表示可继续启动 agent。"""
    import subprocess

    python_exe = sys.executable

    # 1. 快速检测：能 import maa 且版本是 5.x 就直接用（内置包走这条，不联网）
    try:
        import maa  # noqa: F401
    except ImportError:
        print("[MaaKOG] maafw 未安装，准备自动安装", flush=True)
    else:
        try:
            from importlib.metadata import PackageNotFoundError, version

            installed = version("maafw")
            if installed.lstrip("vV").startswith("5."):
                print(f"[MaaKOG] maafw {installed} 已就绪", flush=True)
                return True
            print(f"[MaaKOG] maafw 版本 {installed} 不兼容，需安装 {_MAAFW_REQUIRED_VERSION}", flush=True)
        except PackageNotFoundError:
            pass

    # 2. 确认 pip 可用
    try:
        subprocess.run([python_exe, "-m", "pip", "--version"], capture_output=True, check=True, timeout=30)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        print(
            "[MaaKOG] pip 不可用，无法自动安装 maafw。\n"
            "请手动安装 Python 并勾选 Add Python to PATH，然后执行：\n"
            f"  {python_exe} -m ensurepip\n"
            f"  {python_exe} -m pip install maafw=={_MAAFW_REQUIRED_VERSION}",
            file=sys.stderr,
            flush=True,
        )
        return False

    # 3. 安装：直连 → 清华镜像 → --user 四级回退
    base = [python_exe, "-m", "pip", "install", f"maafw=={_MAAFW_REQUIRED_VERSION}"]
    mirror = ["-i", "https://pypi.tuna.tsinghua.edu.cn/simple"]
    strategies = [
        ("直连 PyPI", base),
        ("清华镜像", base + mirror),
        ("直连 + --user", base + ["--user"]),
        ("清华镜像 + --user", base + ["--user"] + mirror),
    ]
    for label, cmd in strategies:
        print(f"[MaaKOG] 安装 maafw（{label}）...", flush=True)
        try:
            subprocess.check_call(cmd, timeout=_PIP_INSTALL_TIMEOUT)
        except subprocess.TimeoutExpired:
            print(f"[MaaKOG] {label} 超时，尝试下一个...", flush=True)
            continue
        except subprocess.CalledProcessError:
            print(f"[MaaKOG] {label} 失败，尝试下一个...", flush=True)
            continue
        # 安装后校验并刷新模块缓存（本进程后续要 import maa）
        import importlib

        importlib.invalidate_caches()
        for mod in [k for k in list(sys.modules) if k == "maa" or k.startswith("maa.")]:
            del sys.modules[mod]
        print(f"[MaaKOG] maafw 安装成功（{label}）", flush=True)
        return True

    print(
        f"[MaaKOG] maafw 自动安装全部失败。请手动执行：\n"
        f"  {python_exe} -m pip install maafw=={_MAAFW_REQUIRED_VERSION}",
        file=sys.stderr,
        flush=True,
    )
    return False


def main():
    if not _ensure_maafw():
        sys.exit(1)

    # maafw 就绪后再 import（否则缺包时 import 阶段直接崩，走不到自动安装）
    from maa.agent.agent_server import AgentServer
    from maa.toolkit import Toolkit

    import compare_numbers  # noqa: F401
    import my_action  # noqa: F401

    Toolkit.init_option("./")

    if len(sys.argv) < 2:
        sys.stderr.write("Usage: python main.py <socket_id>\n")
        sys.exit(1)

    socket_id = sys.argv[-1]

    AgentServer.start_up(socket_id)
    AgentServer.join()
    AgentServer.shut_down()


if __name__ == "__main__":
    main()
