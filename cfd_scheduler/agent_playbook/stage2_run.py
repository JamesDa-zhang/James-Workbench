# -*- coding: utf-8 -*-
"""
三、正确路径执行：装配配置与解释器 → 复用 Scheduler 跑 网格→求解→后处理。

配置来源优先级：
  1) --config 提供的 JSON（推荐，物理以自然语言填写）
  2) 否则由 --geometry/--output 生成最小配置（fluid_region_rules 为占位时拒绝执行）
解释器来源：--interpreter 文件 → 工作目录 interpreter_runtime.py → NullInterpreter（警告）。
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))  # 使 cfd_scheduler 包可导入

from cfd_scheduler import FlowConfig, NullInterpreter, Scheduler  # noqa: E402


def load_interpreter(path: str | None):
    for p in (path, os.path.join(os.getcwd(), "interpreter_runtime.py")):
        if not p or not os.path.isfile(p):
            continue
        spec = importlib.util.spec_from_file_location("runtime_interpreter", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "build_interpreter"):
            return mod.build_interpreter()
        raise RuntimeError(f"{p} 缺少 build_interpreter() 入口")
    print("[warn] 未找到解释器：物理设置将只记录不执行（NullInterpreter）。"
          "请实现 interpreter_runtime.py 后重跑。", flush=True)
    return NullInterpreter()


def build_config(args) -> FlowConfig:
    if args.config:
        cfg = FlowConfig.from_file(args.config)
    else:
        cfg = FlowConfig.from_dict({
            "name": os.path.basename(args.geometry or "run"),
            "output_root": args.output,
            "mesh": {
                "geometry_file": args.geometry,
                "fluid_region_rules": [],  # 必须由配置/AI 填写真实正则
            },
        })
    if cfg.mesh.geometry_file:
        cfg.mesh.geometry_file = os.path.abspath(cfg.mesh.geometry_file)
    else:
        cfg.mesh.geometry_file = os.path.abspath(args.geometry)
    return cfg


def main() -> int:
    parser = argparse.ArgumentParser(description="正确路径执行（网格→求解→后处理）")
    parser.add_argument("--geometry", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--config", default=None)
    parser.add_argument("--interpreter", default=None)
    parser.add_argument("--stages", default="mesh,solve,post")
    args = parser.parse_args()

    if not args.config and not args.geometry:
        print("请提供 --geometry（或 --config，其中含 geometry_file）", file=sys.stderr)
        return 2

    cfg = build_config(args)
    if not cfg.mesh.fluid_region_rules or any(
        "正则" in r or r.startswith("<") for r in cfg.mesh.fluid_region_rules
    ):
        print("[stop] mesh.fluid_region_rules 为空或仍是占位符："
              "请先用探针读取命名选择，再填入真实正则（决定哪些区域是流体）。", flush=True)
        return 3
    if not cfg.output_root:
        print("[stop] 缺少 output_root", file=sys.stderr)
        return 2

    interp = load_interpreter(args.interpreter)
    sch = Scheduler(cfg, interpreter=interp)
    outcomes = sch.run([s.strip() for s in args.stages.split(",") if s.strip()])
    for name, r in outcomes.items():
        print(f"[{name}] {'OK' if r.ok else 'FAIL'}: {r.message}", flush=True)
        for a in r.artifacts:
            print(f"   产物: {a}", flush=True)
    return 0 if all(r.ok for r in outcomes.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
