# -*- coding: utf-8 -*-
"""
stages_post.py — 后处理阶段。

机械部分（与项目无关）：
  - 会话启动必须 graphics_driver="dx11"（血泪：null 驱动渲染空白）
  - TUI 存图一律经无空格暂存目录（血泪 #5），再复制到 results
  - 残差曲线 matplotlib 化
  - 报告类提取（如出口温度）失败时写"手动步骤说明"（血泪：TUI 表面报告不可靠）
选择部分：画什么图、什么截面、什么曲线、提取什么量 → 经 PhysicsInterpreter.apply_post
  （post_ctx 提供 make_contour / create_axis_plane / save_picture 机械辅助）。
"""
from __future__ import annotations

import os
import shutil
import time
from typing import Any, List, Optional

from . import lessons
from .scheduler import RunContext, StageResult


class PostHelpers:
    """交给解释器的机械辅助（不含任何具体物理量）。"""

    def __init__(self, solver, res_dir: str, stage_dir: str) -> None:
        self.solver = solver
        self.res_dir = res_dir
        self.stage_dir = stage_dir

    def make_contour(self, name: str, field: str, surfaces: List[str], out: str) -> str:
        """在给定表面上渲染 field 云图并保存为 PNG（路径无空格处理内置）。"""
        g = self.solver.settings.results.graphics
        g.contour[name] = {}
        c = g.contour[name]
        c.field = field
        c.surfaces_list = surfaces
        c.display()
        time.sleep(2)
        return self.save_picture(out)

    def create_axis_plane(self, name: str, method: str, coord_key: str, coord_val: float) -> str:
        """创建轴对齐截面平面（method 如 yz-plane / zx-plane / xy-plane）。"""
        ps = self.solver.settings.results.surfaces.plane_surface
        ps.create(name)
        pl = ps[name]
        pl.method = method
        setattr(pl, coord_key, coord_val)
        return name

    def allowed_surfaces(self) -> List[str]:
        g = self.solver.settings.results.graphics
        g.contour["_probe"] = {}
        try:
            return list(g.contour["_probe"].surfaces_list.get_attr("allowed-values"))
        except Exception:
            return []

    def save_picture(self, name: str) -> str:
        """TUI 存图：先存无空格暂存目录，再复制到 results（血泪 #5）。"""
        ok, msg = lessons.check_tui_path_no_space(self.stage_dir)
        if not ok:
            raise RuntimeError(msg)
        stage = os.path.join(self.stage_dir, name)
        self.solver.tui.display.re_render()
        time.sleep(1)
        self.solver.tui.display.save_picture(stage)
        time.sleep(1)
        dst = os.path.join(self.res_dir, name)
        if os.path.isfile(stage):
            shutil.copy2(stage, dst)
        return dst


def _plot_residual_curve(csv_path: str, out_png: str) -> Optional[str]:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import csv as _csv

        cols = ["iter", "continuity", "x-velocity", "y-velocity",
                "z-velocity", "energy", "k", "epsilon"]
        data = {c: [] for c in cols}
        with open(csv_path, "r", newline="") as fh:
            for row in _csv.DictReader(fh):
                for c in cols:
                    try:
                        data[c].append(float(row[c]))
                    except (ValueError, KeyError):
                        pass
        if not data["iter"]:
            return None
        fig, ax = plt.subplots(figsize=(9, 5.5))
        for c in cols[1:]:
            ax.semilogy(data["iter"], data[c], label=c, linewidth=1.2)
        ax.set_xlabel("Iteration")
        ax.set_ylabel("Residual")
        ax.set_title("Residual convergence")
        ax.grid(True, which="both", alpha=0.3)
        ax.legend(fontsize=8, ncol=2)
        fig.tight_layout()
        fig.savefig(out_png, dpi=150)
        plt.close(fig)
        return out_png
    except Exception as exc:
        print(f"[residual-plot] 失败：{exc}", flush=True)
        return None


def stage_post(ctx: RunContext) -> StageResult:
    cfg = ctx.config
    sol_stem = ctx.results.get("solution_stem")
    if not sol_stem:
        return StageResult(stage="post", ok=False, message="缺少求解产物（solve 阶段未成功）")

    import ansys.fluent.core as pyfluent

    res_dir = ctx.out("results")
    stage_dir = cfg.post.stage_dir_no_space or res_dir
    ok, msg = lessons.check_tui_path_no_space(stage_dir)
    if not ok:
        return StageResult(stage="post", ok=False, message=msg)

    solver = None
    artifacts: List[str] = []
    try:
        factory = ctx.fluent_factory or pyfluent.launch_fluent
        solver = factory(
            mode="solver",
            precision=cfg.solver.precision,
            processor_count=cfg.solver.processors,
            ui_mode="hidden_gui",
            graphics_driver="dx11",   # 血泪：没有它渲染出来是空白
            start_transcript=True,
        )
        solver.settings.file.read_case_data(file_name=sol_stem + ".cas")

        helpers = PostHelpers(solver, res_dir, stage_dir)

        # 云图/截面/XY/报告：交给解释器（自然语言 → PyFluent 调用）
        try:
            produced = ctx.interpreter.apply_post(solver, helpers) or []
            artifacts.extend(p for p in produced if p and os.path.isfile(p))
        except Exception as exc:
            print(f"[post-interpreter] 异常：{exc}；自然语言需求已记录", flush=True)
        with open(os.path.join(res_dir, "post_requirements.txt"), "w", encoding="utf-8") as fh:
            fh.write("云图需求：\n" + "\n".join(cfg.post.contours) + "\n\n")
            fh.write("截面需求：\n" + "\n".join(cfg.post.sections) + "\n\n")
            fh.write("XY 需求：\n" + "\n".join(cfg.post.xy_plots) + "\n\n")
            fh.write("报告需求：\n" + "\n".join(cfg.post.reports) + "\n")

        # 残差曲线（机械步骤）
        csv_path = ctx.results.get("residuals_csv")
        if csv_path and os.path.isfile(csv_path):
            png = _plot_residual_curve(csv_path, os.path.join(res_dir, "residuals.png"))
            if png:
                artifacts.append(png)

        # 报告类提取的已知障碍提示（血泪记录）
        if cfg.post.reports:
            with open(os.path.join(res_dir, "reports_note.txt"), "w", encoding="utf-8") as fh:
                fh.write(
                    "工程量提取注意（血泪记录）：\n"
                    "TUI /report/surface-integrals 在本环境曾出现 'Invalid surface' 解析问题；\n"
                    "PyFluent 0.42 无 field_data 服务。\n"
                    "优先在解释器中用 settings.report_definitions 或输出到文件；\n"
                    "仍失败时把需求写入本文件同目录的 post_requirements.txt，"
                    "并提示使用者在 GUI 中按 Results→Reports 手动读取。\n"
                )

        return StageResult(
            stage="post", ok=True,
            message=f"后处理完成：{len(artifacts)} 个产物",
            artifacts=artifacts,
        )
    except Exception as exc:
        import traceback
        return StageResult(
            stage="post", ok=False,
            message=f"{type(exc).__name__}: {exc}",
            traceback=traceback.format_exc(),
        )
    finally:
        if solver is not None:
            try:
                solver.exit()
            except Exception:
                pass
