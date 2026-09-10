# -*- coding: utf-8 -*-
"""
stages_meshing.py — 网格阶段（两段式，血泪 #4/#6 的答案）。

会话A：水密工作流（复制导入→尺寸→面网格→描述→边界→区域）
      → TUI 分步改区域类型（fluid 规则来自配置）→ 逐名称校验 → save_workflow → 退出
会话B：全新会话 load_workflow（干净控制台）→ 体网格 → datamodel WriteCase 落盘 → 退出

物理无关：本阶段不出现任何具体区域名/材料名/物理数值。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import time
from typing import Any, List, Tuple

from . import lessons
from .scheduler import RunContext, StageResult


def _to_list(v) -> list:
    if isinstance(v, (list, tuple)):
        return list(v)
    if isinstance(v, str):
        try:
            return json.loads(v.replace("'", '"'))
        except Exception:
            return []
    try:
        return list(v)
    except Exception:
        return []


def _launch(ctx: RunContext):
    import ansys.fluent.core as pyfluent

    factory = ctx.fluent_factory or pyfluent.launch_fluent
    return factory(
        mode="meshing",
        precision=ctx.config.solver.precision,
        processor_count=ctx.config.solver.processors,
        ui_mode="hidden_gui",
        graphics_driver="dx11",     # 血泪：hidden 默认 null 驱动不渲染
        start_transcript=True,
    )


def _change_region_to_fluid(meshing: Any, obj_name: str, region: str) -> None:
    """血泪 #4：分步交互 + 空行收尾，不留脏控制台。"""
    vr = meshing.tui.objects.volumetric_regions
    try:
        vr.change_type()
    except Exception:
        pass
    time.sleep(1.5)
    meshing.execute_tui(obj_name)
    time.sleep(1.5)
    meshing.execute_tui(region)
    time.sleep(1.5)
    meshing.execute_tui("fluid")
    time.sleep(1.5)
    meshing.execute_tui("")   # 空行结束区域循环
    time.sleep(1.5)


def _region_pairs(wf) -> List[Tuple[str, str]]:
    cur = wf.update_regions.arguments()
    names = _to_list(cur.get("region_current_list"))
    types = [str(t) for t in _to_list(cur.get("region_current_type_list"))]
    return list(zip(names, types))


def stage_meshing(ctx: RunContext) -> StageResult:
    cfg = ctx.config
    mesh_cfg = cfg.mesh
    mesh_dir = ctx.out("mesh")
    wft = os.path.join(mesh_dir, "workflow.wft")
    out_case = os.path.join(mesh_dir, "mesh.cas.h5")
    artifacts: List[str] = []

    # ---- 检查点：fluid 规则必须提供（血泪 #1 的源头） ----
    if not mesh_cfg.fluid_region_rules:
        return StageResult(
            stage="mesh", ok=False,
            message="配置缺少 mesh.fluid_region_rules（区域划分规则），拒绝开始",
        )

    meshing = None
    try:
        # ================= 会话 A =================
        meshing = _launch(ctx)
        wf = meshing.watertight()

        # 复制后导入（血泪 #6：规避 CAD 文件锁）
        tmpdir = tempfile.mkdtemp(prefix="sched_geom_")
        tmp_geom = os.path.join(tmpdir, "input_copy" + os.path.splitext(mesh_cfg.geometry_file)[1])
        shutil.copy2(mesh_cfg.geometry_file, tmp_geom)
        wf.import_geometry.arguments.set_state(
            {"file_name": tmp_geom, "length_unit": mesh_cfg.length_unit}
        )
        wf.import_geometry.Execute()

        # 尺寸函数：界面 min 加密、域内 max 粗化（数值全部来自配置）
        wf.add_local_sizing.AddChildAndUpdate({
            "type": "Curvature",
            "curvature_normal_angle": 18,
            "min_size": mesh_cfg.min_size,
            "max_size": mesh_cfg.max_size,
            "growth_rate": mesh_cfg.growth_rate,
        })
        wf.create_surface_mesh.arguments.set_state({
            "cfd_surface_mesh_controls": {
                "min_size": mesh_cfg.min_size,
                "max_size": mesh_cfg.max_size,
            }
        })
        wf.create_surface_mesh.Execute()
        wf.describe_geometry.arguments.set_state(
            {"setup_type": mesh_cfg.describe_geometry}
        )
        wf.describe_geometry.Execute()
        wf.update_boundaries.Execute()
        wf.update_regions.Execute()

        # 区域类型：fluid 规则正则判定；其余 solid；分步 TUI 修改（血泪 #4）
        pairs = _region_pairs(wf)
        if not pairs:
            return StageResult(stage="mesh", ok=False, message="未读取到区域列表")
        ok, msg = lessons.check_region_rules_cover(pairs, mesh_cfg.fluid_region_rules)
        if not ok:
            return StageResult(stage="mesh", ok=False, message=msg)
        obj_name = "input_copy"   # 复制导入产生的对象名（本流程固定为 input_copy）
        for name, rtype in pairs:
            want_fluid = any(re.search(r, name) for r in mesh_cfg.fluid_region_rules)
            if want_fluid and not rtype.lower().startswith("fluid"):
                _change_region_to_fluid(meshing, obj_name, name)
            elif not want_fluid and not rtype.lower().startswith("solid"):
                # 非 fluid 规则命中的区域保持 solid（默认分类一般已是 solid）
                pass

        # 逐名称精确校验（血泪 #1：数量对不算对）
        pairs = _region_pairs(wf)
        ok, msg = lessons.check_region_type_pairs(pairs, mesh_cfg.fluid_region_rules)
        if not ok:
            return StageResult(stage="mesh", ok=False, message=msg)

        # 存档（血泪 #4：脏控制台隔离在会话 A）
        wf.save_workflow(wft)
        artifacts.append(wft)
        meshing.exit()
        meshing = None

        # ================= 会话 B（干净控制台） =================
        meshing = _launch(ctx)
        wf = meshing.load_workflow(wft)
        vm = wf.create_volume_mesh
        vm.arguments.set_state({"volume_fill": mesh_cfg.volume_fill})
        vm.Execute()

        # datamodel 落盘（不经过 TUI，血泪 #4/#5）
        written = False
        for kw in ({"FileName": out_case}, {"file_name": out_case}):
            try:
                meshing.meshing.File.WriteCase(**kw)
                written = True
                break
            except Exception:
                continue
        if not written or not os.path.isfile(out_case):
            return StageResult(stage="mesh", ok=False, message="网格落盘失败")
        artifacts.append(out_case)

        ctx.results["mesh_case"] = out_case
        ctx.results["workflow_wft"] = wft
        return StageResult(
            stage="mesh", ok=True,
            message=f"网格完成并落盘：{out_case}",
            artifacts=artifacts,
        )
    except Exception as exc:
        import traceback
        return StageResult(
            stage="mesh", ok=False,
            message=f"{type(exc).__name__}: {exc}",
            traceback=traceback.format_exc(),
        )
    finally:
        if meshing is not None:
            try:
                meshing.exit()
            except Exception:
                pass
