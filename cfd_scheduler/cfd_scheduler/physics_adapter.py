# -*- coding: utf-8 -*-
"""
physics_adapter.py — 物理解释器协议与辅助访问器。

原则：代码零物理硬编码。所有物理内容以自然语言字符串进入这里，
由运行时解释器（通常是一名 AI，或一个项目专属的实现文件）翻译为 PyFluent 调用。
本文件只定义"接口形状"与"通用访问器"，不包含任何具体物理数值或模型名。
"""
from __future__ import annotations

from typing import Any, Dict, List, Protocol, runtime_checkable


@runtime_checkable
class PhysicsInterpreter(Protocol):
    """运行时物理解释器：把自然语言指令翻译为 PyFluent settings 调用。"""

    def apply_models(self, solver: Any, nl_text: str) -> None:
        """按 nl_text 设置物理模型（湍流、能量、多相……）。"""

    def apply_materials(self, solver: Any, nl_text: str) -> None:
        """按 nl_text 创建/设置材料物性并分配到区域。"""

    def apply_boundary_conditions(self, solver: Any, nl_text: str) -> None:
        """按 nl_text 设置边界条件数值。"""

    def apply_methods_and_controls(self, solver: Any, nl_text: str) -> None:
        """按 nl_text 设置求解方法、离散格式、松弛因子、初始化。"""

    def setup_monitors(self, solver: Any, nl_text: str) -> None:
        """按 nl_text 设置监测物理量（压降、流量、温度……）。"""

    def apply_post(self, solver: Any, post_ctx: Any) -> List[str]:
        """按后处理自然语言条目生成云图/截面/XY/报告，返回产物路径列表。
        post_ctx 提供 make_contour / create_axis_plane / save_picture 等机械辅助。"""


class NullInterpreter:
    """空解释器：不执行任何物理设置，只记录收到的指令。

    用途：
      - 离线测试/干跑（不启动 Fluent 也能走通调度器骨架）；
      - 提醒未来 AI：物理部分尚未实现，需要提供真实解释器。
    """

    def __init__(self) -> None:
        self.received: Dict[str, str] = {}

    def _record(self, key: str, nl_text: str) -> None:
        self.received[key] = nl_text
        print(f"[NullInterpreter] 收到 {key} 指令（未执行）：{nl_text[:120]}", flush=True)

    def apply_models(self, solver, nl_text: str) -> None:
        self._record("models", nl_text)

    def apply_materials(self, solver, nl_text: str) -> None:
        self._record("materials", nl_text)

    def apply_boundary_conditions(self, solver, nl_text: str) -> None:
        self._record("boundary_conditions", nl_text)

    def apply_methods_and_controls(self, solver, nl_text: str) -> None:
        self._record("methods_and_controls", nl_text)

    def setup_monitors(self, solver, nl_text: str) -> None:
        self._record("monitors", nl_text)

    def apply_post(self, solver, post_ctx) -> List[str]:
        self._record("post", str(post_ctx))
        return []


# ---------------------------------------------------------------------------
# 通用访问器：帮解释器快速拿到"形状"，不含任何物理值
# ---------------------------------------------------------------------------

def fluid_zones(solver) -> List[str]:
    """返回全部流体 cell zone 名称。"""
    try:
        return list(solver.settings.setup.cell_zone_conditions.fluid.keys())
    except Exception:
        return []


def solid_zones(solver) -> List[str]:
    """返回全部固体 cell zone 名称。"""
    try:
        return list(solver.settings.setup.cell_zone_conditions.solid.keys())
    except Exception:
        return []


def boundary_groups(solver) -> Dict[str, List[str]]:
    """返回各类边界组名称（velocity_inlet / pressure_outlet / wall ...）。"""
    out: Dict[str, List[str]] = {}
    try:
        bc = solver.settings.setup.boundary_conditions
        for grp in ("velocity_inlet", "pressure_outlet", "wall",
                    "mass_flow_inlet", "interior", "interface", "symmetry"):
            try:
                out[grp] = list(getattr(bc, grp).keys())
            except Exception:
                continue
    except Exception:
        pass
    return out


def adjacent_cell_zone(bc_object) -> str:
    """返回某边界对象相邻的 cell zone 名（用于判断该边界属于哪个流体域）。"""
    try:
        return str(bc_object.adjacent_cell_zone())
    except Exception:
        return ""


def material_create_fluid(solver, name: str):
    """创建流体材料并返回其对象（物性由解释器设置）。"""
    return solver.settings.setup.materials.fluid.create(name)


def material_create_solid(solver, name: str):
    """创建固体材料并返回其对象。"""
    return solver.settings.setup.materials.solid.create(name)
