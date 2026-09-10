# -*- coding: utf-8 -*-
"""
二、几何输入：提醒用户提供 SpaceClaim 前处理文件，并校验。

要求（写入提醒语，程序只校验存在性与扩展名）：
  - 已抽取流体域（必要时含固体域）
  - 带命名选择（入口/出口/壁面/固体的名字），这是边界与区域自动化的前提
  - 扩展名 .scdoc 或 .pmdb；单位不明默认 mm
"""
from __future__ import annotations

import argparse
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REMINDER = (
    "【需要几何输入】请用户提供 SpaceClaim 前处理后的文件：\n"
    "  1) 格式 .scdoc 或 .pmdb；\n"
    "  2) 已抽取流体域（需要固体时一并保留）；\n"
    "  3) 带命名选择（named selections）：每个入口、出口、壁面、固体区域都要有名字；\n"
    "  4) 单位（默认按 mm；不确定就先用 mm，描述几何步骤会报告尺寸供复核）。\n"
    "拿到文件路径后重新执行：python stage1_input.py --geometry <路径>"
)


def collect_geometry(path: str | None):
    if not path:
        print(REMINDER, flush=True)
        return None
    p = os.path.abspath(path)
    if not os.path.isfile(p):
        print(REMINDER, flush=True)
        print(f"（当前路径不存在：{p}）", flush=True)
        return None
    ext = os.path.splitext(p)[1].lower()
    if ext not in (".scdoc", ".pmdb"):
        print(REMINDER, flush=True)
        print(f"（扩展名不支持：{ext}，请重新导出为 .scdoc/.pmdb）", flush=True)
        return None
    size = os.path.getsize(p)
    if size <= 0:
        print(REMINDER, flush=True)
        print("（文件大小为 0，请重新导出）", flush=True)
        return None
    print(f"GEOMETRY_OK {p} ({size} bytes)", flush=True)
    return p


def main() -> int:
    parser = argparse.ArgumentParser(description="几何输入收集与校验")
    parser.add_argument("--geometry", default=None, help="SpaceClaim 前处理文件路径")
    args = parser.parse_args()
    p = collect_geometry(args.geometry)
    return 0 if p else 2


if __name__ == "__main__":
    sys.exit(main())
