# -*- coding: utf-8 -*-
"""
一、部署与连接检查：让 Agent 能直接用 PyFluent 操控本机 Fluent。

检查项：
  1) Python 与 PyFluent 版本（0.42.* 只支持 Fluent 24.2/25.1/25.2）
  2) 本机 Fluent 可执行文件定位（AWP_ROOT* 环境变量 / 标准安装目录）
  3) 可选连接探针（--probe）：真实启动一次求解会话确认 license 与 gRPC 通路
"""
from __future__ import annotations

import argparse
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_ANSYS_DIRS = (r"C:\Program Files\ANSYS Inc", r"D:\Ansys\ANSYS Inc")


def check_pyfluent() -> tuple:
    try:
        import ansys.fluent.core as pyfluent
        try:
            ver = pyfluent.__version__
        except Exception:
            ver = "unknown"
        return True, f"PYFLUENT_OK version={ver}"
    except Exception as exc:
        return False, f"PYFLUENT_MISSING: {exc}（pip install ansys-fluent-core==0.42.*）"


def find_fluent_exe() -> tuple:
    def _ver(exe: str) -> int:
        m = re.search(r"v(\d{3})", exe)
        return int(m.group(1)) if m else 0

    candidates = []
    for var, val in sorted(os.environ.items()):
        if var.startswith("AWP_ROOT") and val:
            exe = os.path.join(val, "fluent", "ntbin", "win64", "fluent.exe")
            if exe not in candidates:
                candidates.append(exe)
    for base in _ANSYS_DIRS:
        if os.path.isdir(base):
            for entry in sorted(os.listdir(base), reverse=True):
                if entry.lower().startswith("v") and entry[1:].isdigit():
                    candidates.append(
                        os.path.join(base, entry, "fluent", "ntbin", "win64", "fluent.exe")
                    )
    # 只保留存在的，并选最高版本（PyFluent 0.42 只支持 24.2+，v221 应被跳过）
    found = [exe for exe in candidates if os.path.isfile(exe)]
    found.sort(key=_ver, reverse=True)
    if found:
        ver = _ver(found[0])
        note = "" if ver >= 242 else f"（注意：最高版本 v{ver} 低于 PyFluent 0.42 支持的 24.2，连接会失败）"
        return ver >= 242, f"FLUENT_FOUND {found[0]}{note}"
    return False, "FLUENT_NOT_FOUND: 未找到 fluent.exe（请安装 Fluent 24.2+ 或设置 AWP_ROOT242）"


def probe_connection() -> tuple:
    import ansys.fluent.core as pyfluent

    solver = None
    try:
        solver = pyfluent.launch_fluent(
            mode="solver", precision="double", processor_count=2,
            ui_mode="hidden_gui",
        )
        ver = solver.get_fluent_version()
        return True, f"LAUNCH_OK version={ver}（Agent 可直接用 PyFluent 操控 Fluent）"
    except Exception as exc:
        return False, f"LAUNCH_FAILED: {exc}"
    finally:
        if solver is not None:
            try:
                solver.exit()
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description="部署与连接检查")
    parser.add_argument("--probe", action="store_true",
                        help="真实启动一次 Fluent 会话验证连接（约 1-2 分钟）")
    args = parser.parse_args()

    ok_all = True
    for name, (ok, msg) in (
        ("PyFluent", check_pyfluent()),
        ("Fluent", find_fluent_exe()),
    ):
        print(f"[{'OK' if ok else 'FAIL'}] {msg}", flush=True)
        ok_all = ok_all and ok

    if args.probe and ok_all:
        ok, msg = probe_connection()
        print(f"[{'OK' if ok else 'FAIL'}] {msg}", flush=True)
        ok_all = ok_all and ok
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
