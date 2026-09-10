# -*- coding: utf-8 -*-
"""playbook 离线测试（不启动 Fluent）。"""
import csv
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import stage1_input
import stage3_evaluate

PASS = 0
FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}  {extra}")


def test_stage1():
    print("[test] stage1 几何输入校验")
    r = stage1_input.collect_geometry(None)
    check("无路径返回 None（并打印提醒）", r is None)
    r = stage1_input.collect_geometry("Z:/不存在.scdoc")
    check("不存在路径返回 None", r is None)
    tmp = tempfile.NamedTemporaryFile(suffix=".scdoc", delete=False)
    tmp.write(b"x" * 100)
    tmp.close()
    r = stage1_input.collect_geometry(tmp.name)
    check("合法 .scdoc 通过", r is not None)
    os.unlink(tmp.name)
    bad = tempfile.NamedTemporaryFile(suffix=".stp", delete=False)
    bad.close()
    r = stage1_input.collect_geometry(bad.name)
    check("非法扩展名被拒", r is None)
    os.unlink(bad.name)


def test_stage3():
    print("[test] stage3 结果评价")
    tmp = tempfile.mkdtemp(prefix="eval_test_")
    os.makedirs(os.path.join(tmp, "results"), exist_ok=True)
    with open(os.path.join(tmp, "results", "residuals.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["iter", "continuity", "x-velocity", "y-velocity",
                    "z-velocity", "energy", "k", "epsilon"])
        w.writerow([400, 0.329, 7e-5, 7e-5, 7e-5, 3.7e-6, 1.3e-3, 1.2e-3])
    report = stage3_evaluate.evaluate(tmp, 5e-3)
    check("生成评价报告", "结论" in report)
    check("平台震荡判定正确", "疑似回流" in report)
    report2 = stage3_evaluate.evaluate(tmp, 0.5)
    check("阈值内判收敛", "**结论：收敛**" in report2)


if __name__ == "__main__":
    test_stage1()
    test_stage3()
    print(f"\n===== playbook 离线测试：PASS {PASS} / FAIL {FAIL} =====")
    sys.exit(0 if FAIL == 0 else 1)
