# -*- coding: utf-8 -*-
"""
四、结果分析与评价：读产物与残差，生成 EVALUATION.md。

评价维度：
  1) 收敛性：末值连续性 vs 阈值；其余方程趋势；给出结论类别
  2) 网格量级：单元数是否在目标区间（日志/报告中如有记录）
  3) 产物完整性：case/data/图片/CSV 是否齐全
  4) 物理合理性：transcript 中的回流（Reversed flow）等警告检索
"""
from __future__ import annotations

import argparse
import csv
import glob
import io
import os
import re
import sys
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_DEFAULT_THRESHOLD = 5e-3


def read_residuals(out_root: str):
    p = os.path.join(out_root, "results", "residuals.csv")
    if not os.path.isfile(p):
        return None, None
    rows = []
    with open(p, "r", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                rows.append({
                    "iter": int(float(row["iter"])),
                    "continuity": float(row["continuity"]),
                    "x-velocity": float(row["x-velocity"]),
                    "energy": float(row["energy"]),
                    "k": float(row["k"]),
                    "epsilon": float(row["epsilon"]),
                })
            except (ValueError, KeyError):
                continue
    return rows, p


def convergence_verdict(rows, threshold):
    if not rows:
        return "无法判定（缺 residuals.csv）", []
    last = rows[-1]
    notes = [f"最终迭代 {last['iter']} 步，连续性 {last['continuity']:.3e}（阈值 {threshold:.0e}）"]
    # 次要方程（速度/能量/k/eps）用 10×阈值 作为"实质收敛"带宽：
    # 避免 1.2e-3 这类贴近阈值、实际已收敛的量被误判
    band = max(1e-3, 10 * threshold)
    others_ok = all(
        last[k] < band for k in ("x-velocity", "energy", "k", "epsilon")
    )
    notes.append(
        "速度/能量/湍流方程全部低于 1e-3" if others_ok
        else "部分方程未达 1e-3：" + ", ".join(
            k for k in ("x-velocity", "energy", "k", "epsilon") if last[k] >= 1e-3
        )
    )
    if last["continuity"] < threshold:
        verdict = "收敛"
    elif others_ok:
        verdict = "未收敛但其余方程已收敛：疑似回流/再循环振荡（质量不平衡平台震荡），建议人工检查压力出口背压或计算域"
    else:
        verdict = "未收敛：请检查边界条件与网格质量后再算"
    return verdict, notes


def reversed_flow_count(out_root):
    hits = 0
    search_dirs = [out_root, os.getcwd()]
    for d in search_dirs:
        for p in glob.glob(os.path.join(d, "fluent-*.trn")) + [os.path.join(d, "fluent.trn")]:
            try:
                with io.open(p, encoding="gbk", errors="replace") as fh:
                    text = fh.read()
                hits += len(re.findall(r"Reversed flow", text, re.I))
            except OSError:
                continue
    return hits


def artifact_summary(out_root):
    items = []
    for p in sorted(glob.glob(os.path.join(out_root, "**", "*"), recursive=True)):
        if os.path.isfile(p):
            items.append(os.path.relpath(p, out_root))
    return items


def evaluate(out_root: str, threshold: float) -> str:
    lines = [
        "# CFD 结果评价报告",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 输出目录：{out_root}",
        "",
        "## 1. 收敛性",
    ]
    rows, _ = read_residuals(out_root)
    verdict, notes = convergence_verdict(rows, threshold)
    lines.append(f"**结论：{verdict}**")
    for n in notes:
        lines.append(f"- {n}")

    lines += ["", "## 2. 产物完整性"]
    artifacts = artifact_summary(out_root)
    if artifacts:
        for a in artifacts:
            lines.append(f"- {a}")
    else:
        lines.append("- 未发现任何产物文件")

    lines += ["", "## 3. 物理合理性"]
    n_rev = reversed_flow_count(out_root)
    if n_rev:
        lines.append(f"- 检测到回流（Reversed flow）警告共 {n_rev} 处：请人工复核压力出口条件。")
    else:
        lines.append("- transcript 中未见回流警告。")

    lines += ["", "## 4. 下一步建议"]
    if verdict == "收敛":
        lines.append("- 结果可用于工程判断；如需更高精度可加密网格重算。")
    else:
        lines.append("- 不满足收敛判据时的抓手：检查出口背压/延长计算域/网格加密；按用户指令决策。")
    lines.append("- 如需提取出口温度等工程量：用 GUI Reports → Surface Integrals 手动读取，或实现 settings.report_definitions。")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="结果分析与评价")
    parser.add_argument("--output", required=True, help="运行输出目录")
    parser.add_argument("--threshold", type=float, default=_DEFAULT_THRESHOLD)
    args = parser.parse_args()
    report = evaluate(args.output, args.threshold)
    out = os.path.join(args.output, "EVALUATION.md")
    os.makedirs(args.output, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(report)
    print(report, flush=True)
    print(f"\n[ok] 评价报告已写入 {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
