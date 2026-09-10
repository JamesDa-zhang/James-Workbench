# -*- coding: utf-8 -*-
"""
test_offline.py — 离线测试（不启动 Fluent）。

覆盖：
  1) 配置加载/序列化（含自然语言占位符保留）
  2) 全部检查点守卫（区域逐名校验、内存估算、TUI 路径空格、规则覆盖、残差解析）
  3) 调度器骨架：阶段注册、fail-fast 阻断、报告写出（用假工厂+假解释器干跑）
运行：python test_offline.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cfd_scheduler import FlowConfig, NullInterpreter, Scheduler  # noqa: E402
from cfd_scheduler import lessons  # noqa: E402

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


def test_config():
    print("[test] 配置加载与序列化")
    raw = {
        "name": "t",
        "output_root": "D:/x",
        "mesh": {
            "geometry_file": "g.scdoc",
            "min_size": 2.0, "max_size": 40.0,
            "target_cell_range": [300000, 1200000],
            "fluid_region_rules": ["^zone----"],
        },
        "physics": {"models": "开启能量方程，k-epsilon"},
        "post": {"stage_dir_no_space": "C:/temp/stage"},
    }
    cfg = FlowConfig.from_dict(raw)
    check("name", cfg.name == "t")
    check("fluid_rules", cfg.mesh.fluid_region_rules == ["^zone----"])
    check("nl_models 保留", cfg.physics.models == "开启能量方程，k-epsilon")
    d = cfg.to_dict()
    check("序列化往返", d["mesh"]["min_size"] == 2.0)


def test_lessons():
    print("[test] 检查点守卫")
    pairs = [("zone-----", "fluid"), ("zone-----.1", "fluid"),
             ("shell", "solid"), ("tube", "solid"), ("fins-1", "solid")]
    ok, _ = lessons.check_region_type_pairs(pairs, ["^zone----"])
    check("区域逐名校验通过", ok)

    bad = [("zone-----", "fluid"), ("zone-----.1", "solid"), ("fins-1", "fluid")]
    ok, msg = lessons.check_region_type_pairs(bad, ["^zone----"])
    check("区域位置错必被抓", not ok and "zone-----.1" in msg and "fins-1" in msg, msg)

    ok, _ = lessons.check_region_rules_cover(pairs, ["^zone----"])
    check("规则覆盖命中", ok)
    ok, _ = lessons.check_region_rules_cover(pairs, ["^nothing$"])
    check("规则落空被抓", not ok)

    ok, msg = lessons.check_memory_estimate(6_600_000, 10.0, "double")
    check("6.6M 双精度超预算被抓", not ok, msg)
    ok, _ = lessons.check_memory_estimate(600_000, 12.0, "double")
    check("0.6M 双精度通过", ok)

    ok, msg = lessons.check_tui_path_no_space("C:/a b/c.png")
    check("空格路径被抓", not ok)
    ok, _ = lessons.check_tui_path_no_space("C:/temp/cfd_stage")
    check("无空格路径通过", ok)

    ok, msg = lessons.check_cell_count_in_range(600_000, (300_000, 1_200_000))
    check("量级区间通过", ok)
    ok, _ = lessons.check_cell_count_in_range(6_600_000, (300_000, 1_200_000))
    check("量级超界被抓", not ok)

    text = (
        "iter  scalar-0\n"
        "   9   9.861540e-10\n"
        "  iter  continuity  x-velocity ...\n"
        "   400  3.2926e-01  7.3616e-05  7.2455e-05  6.7387e-05 "
        "3.7413e-06  1.3120e-03  1.1919e-03\n"
    )
    rows = lessons.parse_residual_rows(text)
    check("残差解析只认 8 列（初始化表被排除）",
          len(rows) == 1 and rows[0][0] == 400 and abs(rows[0][1] - 0.32926) < 1e-6)


def test_scheduler_skeleton():
    print("[test] 调度器骨架（fail-fast 与报告）")
    import tempfile as _tf

    tmp = _tf.mkdtemp(prefix="sched_test_")
    raw = {
        "name": "skeleton", "output_root": tmp,
        "mesh": {"geometry_file": "x.scdoc",
                 "target_cell_range": [1, 10],
                 "fluid_region_rules": ["^f"]},
        "solver": {"memory_budget_gb": 1.0},
    }
    cfg = FlowConfig.from_dict(raw)
    sch = Scheduler(cfg, interpreter=NullInterpreter())

    # 注入假阶段，验证 fail-fast
    def ok_stage(ctx):
        from cfd_scheduler.scheduler import StageResult
        return StageResult(stage="s1", ok=True, message="ok", artifacts=[])

    def fail_stage(ctx):
        from cfd_scheduler.scheduler import StageResult
        return StageResult(stage="s2", ok=False, message="boom")

    sch.register("s1", ok_stage)
    sch.register("s2", fail_stage)
    sch.register("s3", ok_stage)
    out = sch.run(["s1", "s2", "s3"])
    check("s1 ok", out["s1"].ok)
    check("s2 fail", not out["s2"].ok)
    check("s3 被阻断", not out["s3"].ok and "阻断" in out["s3"].message)
    check("报告写出", os.path.isfile(os.path.join(tmp, "scheduler_report.json")))


if __name__ == "__main__":
    test_config()
    test_lessons()
    test_scheduler_skeleton()
    print(f"\n===== 离线测试结果：PASS {PASS} / FAIL {FAIL} =====")
    sys.exit(0 if FAIL == 0 else 1)
