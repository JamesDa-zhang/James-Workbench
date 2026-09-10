# -*- coding: utf-8 -*-
"""
lessons.py — 血泪教训固化为检查点守卫。

每一条来自真实失败：
  1) 网格流程区域类型"数量对但位置错"→ 必须逐名称配对校验
  2) set_state 内部会执行命令 → 严禁重复 Execute
  3) 内存不足时双精度求解崩溃（MPI 心跳超时）→ 迭代前估算内存
  4) TUI 控制台脏状态会毒化后续切换/执行 → 分步交互 + 空行收尾 + 会话隔离
  5) TUI 存图路径含空格会被截断 → 一律经无空格暂存目录
  6) SpaceClaim 打开原文件导致 CAD 导入失败 → 复制后导入
  7) 大 case+data 单次写入导致连接重置 → 先 data 后 case、分开写、带重试
  8) 残差解析被混合初始化表格污染 → 只认 8 列残差行
  9) 网格目标量级必须与内存预算匹配 → target_cell_range + 内存估算联动
"""
from __future__ import annotations

import os
import re
from typing import Callable, Dict, List, Tuple

# 通用工程估算：每单元内存占用（字节）。
# 双精度耦合求解（含能量/湍流）经验值 ~3.2KB/单元，单精度 ~1.6KB/单元。
_BYTES_PER_CELL = {"double": 3.2e3, "single": 1.6e3}
_SAFETY_FACTOR = 1.5


def check_memory_estimate(
    cell_count: int,
    memory_budget_gb: float,
    precision: str,
) -> Tuple[bool, str]:
    """检查点：按单元数估算求解内存，超过预算即阻断（血泪 #3）。"""
    if cell_count <= 0:
        return False, f"单元数无效：{cell_count}"
    need_gb = cell_count * _BYTES_PER_CELL.get(precision, 3.2e3) * _SAFETY_FACTOR / 1e9
    if need_gb > memory_budget_gb:
        return False, (
            f"内存风险：{cell_count} 单元 × {precision} 精度估算需 "
            f"{need_gb:.1f}GB > 预算 {memory_budget_gb}GB。"
            f"请增大 max_size 粗化网格或降低预算目标（界面 min_size 保持加密）。"
        )
    return True, f"内存检查通过：估算 {need_gb:.1f}GB <= 预算 {memory_budget_gb}GB"


def check_cell_count_in_range(
    cell_count: int,
    target_range: Tuple[int, int],
) -> Tuple[bool, str]:
    """检查点：网格量级落在目标区间（血泪 #9）。"""
    lo, hi = target_range
    if lo <= cell_count <= hi:
        return True, f"网格量级 {cell_count} 在目标区间 [{lo}, {hi}] 内"
    return False, f"网格量级 {cell_count} 不在目标区间 [{lo}, {hi}]，建议调整 min/max_size"


def check_region_type_pairs(
    pairs: List[Tuple[str, str]],
    fluid_rules: List[str],
) -> Tuple[bool, str]:
    """检查点：区域类型逐名称配对校验（血泪 #1——数量对不算对）。"""
    bad = []
    for name, rtype in pairs:
        is_fluid_rule = any(re.search(r, name) for r in fluid_rules)
        want = "fluid" if is_fluid_rule else "solid"
        if not str(rtype).lower().startswith(want):
            bad.append(f"{name}: 实际={rtype}, 期望={want}")
    if bad:
        return False, "区域类型校验失败：" + "; ".join(bad)
    return True, f"区域类型逐名称校验通过（{len(pairs)} 个区域）"


def check_tui_path_no_space(path: str) -> Tuple[bool, str]:
    """检查点：TUI 存图/传参路径不得含空格（血泪 #5）。"""
    if not path:
        return False, "路径为空"
    if " " in path:
        return False, f"路径含空格，TUI 会被截断：{path}"
    return True, f"TUI 路径安全：{path}"


def check_region_rules_cover(
    pairs: List[Tuple[str, str]],
    fluid_rules: List[str],
) -> Tuple[bool, str]:
    """检查点：fluid 规则至少命中一个区域（规则写反/写空时立即暴露）。"""
    if not fluid_rules:
        return False, "fluid_region_rules 为空：无法判定哪些区域是流体（血泪 #1 的源头）"
    hits = [n for n, _ in pairs if any(re.search(r, n) for r in fluid_rules)]
    if not hits:
        return False, "fluid 规则没有命中任何区域：请检查正则是否写反"
    return True, f"fluid 规则命中区域：{hits}"


def parse_residual_rows(text: str, min_columns: int = 8):
    """残差解析（血泪 #8）：只认 iter+7 残差的 8 列行，避开混合初始化表格。"""
    pat = re.compile(
        r"^\s*(\d+)\s+" + r"\s+".join([r"([\d.eE+\-]+)"] * 7) + r"\s*$",
        re.M,
    )
    rows = []
    for m in pat.finditer(text):
        try:
            rows.append([float(m.group(i)) for i in range(1, 9)])
        except ValueError:
            continue
    return rows


def drain_console(execute_tui: Callable[[str], None], times: int = 3) -> None:
    """血泪 #4 的收尾动作：空行排空控制台，清理残留提示/错误状态。"""
    for _ in range(times):
        try:
            execute_tui("")
        except Exception:
            pass


# 全部教训注册表（供 README 自动生成、供未来 AI 速查）
LESSON_REGISTRY: List[Dict[str, str]] = [
    {
        "id": "L1",
        "title": "区域类型逐名称校验",
        "failure": "区域类型'流体数量对但位置错'（如 fins 被设成 fluid），体网格按错误类型生成",
        "rule": "用 check_region_type_pairs 对 (名称,类型) 逐对核对；fluid 规则命中即 fluid",
    },
    {
        "id": "L2",
        "title": "set_state 内部会执行命令",
        "failure": "set_state 后再次 Execute 导致区域重新分类、覆盖已设类型",
        "rule": "PyFluent 工作流 wrapper 的 arguments.set_state 会立即触发命令执行，严禁重复 Execute",
    },
    {
        "id": "L3",
        "title": "内存预算检查",
        "failure": "6.6M 单元双精度在 15.7GB 机器上迭代即崩（MPI 心跳超时）",
        "rule": "迭代前用 check_memory_estimate 估算；超预算就粗化 max_size、保留界面 min_size",
    },
    {
        "id": "L4",
        "title": "TUI 控制台脏状态",
        "failure": "交互式 TUI 留下错误状态，毒化后续 switch/Execute，表现随机",
        "rule": "分步交互 + 空行收尾 + 排空；网格阶段两段式（会话A存档→会话B干净加载跑体网格+落盘）",
    },
    {
        "id": "L5",
        "title": "TUI 路径不能含空格",
        "failure": "存图路径 C:...CFD study... 在空格处截断，报 invalid command",
        "rule": "TUI 存图一律先写无空格暂存目录，再复制到目标目录（check_tui_path_no_space）",
    },
    {
        "id": "L6",
        "title": "CAD 文件锁",
        "failure": "SpaceClaim 打开 .scdoc 时导入报 AttachAssembly 失败",
        "rule": "导入前先复制几何到临时目录，导入副本",
    },
    {
        "id": "L7",
        "title": "大结果分开写",
        "failure": "case+data 单次写入 500MB+ 导致 gRPC 连接重置，结果丢失",
        "rule": "先写 data 再写 case，分开写并带重试",
    },
    {
        "id": "L8",
        "title": "残差解析防污染",
        "failure": "把混合初始化表格当成求解残差，造成假收敛",
        "rule": "只用 8 列残差行（iter+7 残差）判定；收敛判定放在落盘后、从 transcript 解析",
    },
    {
        "id": "L9",
        "title": "网格量级与目标联动",
        "failure": "按示例尺寸划出的网格远超内存能力",
        "rule": "target_cell_range 写进配置，落盘后校验，超界即调整尺寸重划",
    },
]
