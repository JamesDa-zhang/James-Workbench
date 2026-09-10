# -*- coding: utf-8 -*-
"""
auto_flow.py — 一键入口（插件式）：按正确路径自动完成 0→1→2→3。

用法：
  python auto_flow.py --geometry "D:/work/model.scdoc" --output "D:/work/out"
                     [--config config.json] [--interpreter interpreter_runtime.py] [--skip-probe]

流程：
  0) stage0：环境与连接检查（含 license 探针，可用 --skip-probe 跳过）
  1) stage1：几何输入校验（缺失时打印提醒语）
  2) stage2：网格 → 求解 → 后处理（复用 cfd_scheduler.Scheduler，物理经解释器注入）
  3) stage3：结果评价 → 输出目录生成 EVALUATION.md
"""
from __future__ import annotations

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import stage0_environment  # noqa: E402
import stage1_input  # noqa: E402
import stage2_run  # noqa: E402
import stage3_evaluate  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="CFD 正确路径一键执行（0→1→2→3）")
    parser.add_argument("--geometry", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--config", default=None)
    parser.add_argument("--interpreter", default=None)
    parser.add_argument("--skip-probe", action="store_true")
    parser.add_argument("--stages", default="mesh,solve,post")
    args = parser.parse_args()

    print("========== 0) 部署与连接检查 ==========", flush=True)
    ok0, _ = stage0_environment.check_pyfluent()
    if not ok0:
        print("[stop] PyFluent 不可用，先完成部署（见 AGENT_GUIDE.md 第一节）", flush=True)
        return 1
    okf, msgf = stage0_environment.find_fluent_exe()
    print(msgf, flush=True)
    if not okf:
        return 1
    if not args.skip_probe:
        okp, msgp = stage0_environment.probe_connection()
        print(msgp, flush=True)
        if not okp:
            print("[stop] 连接探针失败：请用户修复 license 后重跑", flush=True)
            return 1

    print("========== 1) 几何输入 ==========", flush=True)
    geom = stage1_input.collect_geometry(args.geometry)
    if not geom:
        return 2
    if not args.output:
        args.output = os.path.join(os.path.dirname(geom), "cfd_out")

    print("========== 2) 正确路径执行 ==========", flush=True)
    sys.argv = [
        "stage2_run", "--geometry", geom, "--output", args.output,
        "--stages", args.stages,
    ]
    if args.config:
        sys.argv += ["--config", args.config]
    if args.interpreter:
        sys.argv += ["--interpreter", args.interpreter]
    rc2 = stage2_run.main()
    if rc2 != 0:
        print(f"[stop] 执行失败（退出码 {rc2}），见上方检查点信息", flush=True)
        return rc2

    print("========== 3) 结果评价 ==========", flush=True)
    rc3 = 0
    try:
        report = stage3_evaluate.evaluate(args.output, 5e-3)
        print(report, flush=True)
        out = os.path.join(args.output, "EVALUATION.md")
        os.makedirs(args.output, exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(report)
        print(f"\n[ok] 评价报告已写入 {out}", flush=True)
    except Exception as exc:
        print(f"[warn] 评价阶段异常：{exc}", flush=True)
        rc3 = 0
    print("========== 完成 ==========", flush=True)
    print(f"输出目录：{args.output}（含 EVALUATION.md 结论页）", flush=True)
    return rc3


if __name__ == "__main__":
    sys.exit(main())
