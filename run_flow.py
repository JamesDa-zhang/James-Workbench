# -*- coding: utf-8 -*-
"""
run_flow.py — 入口：读顶层配置 → 装配解释器 → 跑调度器 → 打印汇总。

解释器装配顺序：
  1) 命令行 --interpreter 指定的 Python 文件（如 my_interpreter.py，内含
     build_interpreter() -> PhysicsInterpreter）；
  2) 同目录 interpreter_runtime.py；
  3) 都没有 → NullInterpreter（只记录不执行，提醒物理尚未实现）。
"""
import argparse
import importlib.util
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cfd_scheduler import FlowConfig, NullInterpreter, Scheduler  # noqa: E402


def load_interpreter(path: str):
    if not path or not os.path.isfile(path):
        return None
    spec = importlib.util.spec_from_file_location("runtime_interpreter", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if hasattr(mod, "build_interpreter"):
        return mod.build_interpreter()
    raise RuntimeError(f"{path} 缺少 build_interpreter() 入口")


def main() -> int:
    parser = argparse.ArgumentParser(description="CFD 流程调度器入口")
    parser.add_argument("--config", required=True, help="顶层 JSON 配置文件路径")
    parser.add_argument("--stages", default="mesh,solve,post",
                        help="逗号分隔的阶段列表（mesh,solve,post）")
    parser.add_argument("--interpreter", default=None,
                        help="运行时解释器 Python 文件（含 build_interpreter()）")
    args = parser.parse_args()

    cfg = FlowConfig.from_file(args.config)
    print(f"[cfg] 项目：{cfg.name}")
    print(f"[cfg] 输出目录：{cfg.output_root}")
    print(f"[cfg] 物理指令（自然语言占位）：")
    for k, v in cfg.to_dict()["physics"].items():
        print(f"   - {k}: {v[:100]}")

    interp = load_interpreter(args.interpreter)
    if interp is None:
        local = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "interpreter_runtime.py")
        interp = load_interpreter(local)
    if interp is None:
        interp = NullInterpreter()
        print("[warn] 未提供解释器：物理设置将只记录不执行（NullInterpreter）")

    sch = Scheduler(cfg, interpreter=interp)
    stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    outcomes = sch.run(stages)

    print("\n===== 汇总 =====")
    for name, r in outcomes.items():
        print(f"[{name}] {'OK' if r.ok else 'FAIL'}: {r.message}")
        for a in r.artifacts:
            print(f"   产物: {a}")
        if r.traceback:
            print(r.traceback)
    return 0 if all(r.ok for r in outcomes.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
