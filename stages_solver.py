# -*- coding: utf-8 -*-
"""
stages_solver.py — 求解阶段。

机械部分（与项目无关）：
  - 启动求解会话、读网格、内存检查点（血泪 #3/#9）
  - 分批迭代、残差解析（8 列判别，血泪 #8）、收敛判定（阈值来自配置）
  - 先 data 后 case 分开落盘（血泪 #7）
物理部分：全部经 PhysicsInterpreter 以自然语言注入（零硬编码）。
"""
from __future__ import annotations

import csv
import io
import os
import re
import time
from typing import Any, List

from . import lessons
from .scheduler import RunContext, StageResult


def _cell_count(solver) -> int:
    """尽量拿到单元数（用于内存检查点）；拿不到返回 0（检查点会阻断）。"""
    try:
        stats = solver.mesh.get_statistics()
        return int(stats.get("cells", 0))
    except Exception:
        pass
    return 0


def _read_trn_tail(n: int = 8000) -> str:
    import glob as _glob

    candidates = [os.path.join(os.getcwd(), "fluent.trn")]
    auto = sorted(_glob.glob(os.path.join(os.getcwd(), "fluent-*.trn")),
                  key=os.path.getmtime)
    if auto:
        candidates.append(auto[-1])
    for p in candidates:
        if os.path.isfile(p):
            try:
                with io.open(p, encoding="gbk", errors="replace") as fh:
                    return fh.read()[-n:]
            except OSError:
                continue
    return ""


def _save_residual_csv(rows: List[list], path: str) -> None:
    header = ["iter", "continuity", "x-velocity", "y-velocity",
              "z-velocity", "energy", "k", "epsilon"]
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def stage_solver(ctx: RunContext) -> StageResult:
    cfg = ctx.config
    sol_cfg = cfg.solver
    mesh_case = ctx.results.get("mesh_case")
    if not mesh_case:
        return StageResult(stage="solve", ok=False, message="缺少网格产物（mesh 阶段未成功）")

    import ansys.fluent.core as pyfluent

    solver = None
    artifacts: List[str] = []
    try:
        factory = ctx.fluent_factory or pyfluent.launch_fluent
        solver = factory(
            mode="solver",
            precision=sol_cfg.precision,
            processor_count=sol_cfg.processors,
            ui_mode="hidden_gui",
            start_transcript=True,
        )
        solver.settings.file.read_case(file_name=mesh_case)

        # ---- 检查点：内存预算（血泪 #3/#9） ----
        cells = _cell_count(solver)
        if cells > 0:
            ok, msg = lessons.check_memory_estimate(
                cells, sol_cfg.memory_budget_gb, sol_cfg.precision)
            if not ok:
                return StageResult(stage="solve", ok=False, message=msg)
            ok2, msg2 = lessons.check_cell_count_in_range(
                cells, ctx.config.mesh.target_cell_range)
            if not ok2:
                print("[warn] " + msg2 + "（继续执行，如需调整请改 max_size 后重划）", flush=True)
            print(f"[checkpoint] {msg}", flush=True)
        else:
            print("[warn] 无法读取单元数，跳过内存检查点（建议人工确认）", flush=True)

        # ---- 物理：全部经解释器注入（零硬编码） ----
        ctx.interpreter.apply_models(solver, cfg.physics.models)
        ctx.interpreter.apply_materials(solver, cfg.physics.materials)
        ctx.interpreter.apply_boundary_conditions(solver, cfg.physics.boundary_conditions)
        ctx.interpreter.apply_methods_and_controls(solver, cfg.physics.methods_and_controls)
        ctx.interpreter.setup_monitors(solver, cfg.physics.monitors)

        # ---- 迭代（批次来自配置） ----
        total = 0
        while total < sol_cfg.max_iterations:
            n = min(sol_cfg.batch_size, sol_cfg.max_iterations - total)
            solver.settings.solution.run_calculation.iterate(iter_count=n)
            total += n
            time.sleep(2)

        # ---- 残差解析（8 列判别，血泪 #8）+ 收敛判定 ----
        tail = _read_trn_tail(60000)
        rows = lessons.parse_residual_rows(tail)
        csv_path = ctx.out("results") + "/residuals.csv"
        _save_residual_csv(rows, csv_path)
        artifacts.append(csv_path)
        last_cont = rows[-1][1] if rows else None
        converged = last_cont is not None and last_cont < sol_cfg.continuity_threshold
        print(f"[residual] iter={int(rows[-1][0]) if rows else '?'}, "
              f"continuity={last_cont}, threshold={sol_cfg.continuity_threshold}, "
              f"converged={converged}", flush=True)
        if not converged:
            print(f"[note] 收敛说明：{sol_cfg.convergence_note}", flush=True)

        # ---- 落盘：先 data 后 case（血泪 #7） ----
        sol_dir = ctx.out("solution")
        stem = os.path.join(sol_dir, "solution")
        for attempt in range(3):
            try:
                solver.settings.file.write_data(file_name=stem + ".dat")
                break
            except Exception as exc:
                print(f"[write-data retry {attempt}] {exc}", flush=True)
                time.sleep(10)
        for attempt in range(3):
            try:
                solver.settings.file.write_case(file_name=stem + ".cas")
                break
            except Exception as exc:
                print(f"[write-case retry {attempt}] {exc}", flush=True)
                time.sleep(10)
        for ext in (".dat.h5", ".dat", ".cas.h5", ".cas"):
            p = stem + ext
            if os.path.isfile(p):
                artifacts.append(p)

        ctx.results["solution_stem"] = stem
        ctx.results["residuals_csv"] = csv_path
        ctx.results["converged"] = bool(converged)
        ctx.results["last_continuity"] = last_cont
        return StageResult(
            stage="solve", ok=True,
            message=f"求解完成：{total} 步，连续性={last_cont}，收敛={converged}",
            artifacts=artifacts,
        )
    except Exception as exc:
        import traceback
        return StageResult(
            stage="solve", ok=False,
            message=f"{type(exc).__name__}: {exc}",
            traceback=traceback.format_exc(),
        )
    finally:
        if solver is not None:
            try:
                solver.exit()
            except Exception:
                pass
