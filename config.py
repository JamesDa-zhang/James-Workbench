# -*- coding: utf-8 -*-
"""
config.py — 顶层轻量级配置模型。

原则：代码零物理硬编码。一切项目相关量（几何、网格尺寸、区域划分规则、
物理模型、材料、边界条件、松弛因子、监测量、后处理需求）都由外部配置传入；
物理类条目以自然语言文本承载，由运行时解释器（AI）翻译为 PyFluent 调用。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, List, Tuple


@dataclass
class MeshConfig:
    """网格阶段配置。"""
    geometry_file: str = ""
    length_unit: str = "mm"            # 导入单位：m / mm / cm ...
    min_size: float = 2.0              # 界面/曲面最小尺寸（单位同 length_unit）
    max_size: float = 40.0             # 域内部最大尺寸
    growth_rate: float = 1.2
    volume_fill: str = "poly-hexcore"  # 体网格填充方式（Fluent 选项名）
    describe_geometry: str = (
        "The geometry consists of both fluid and solid regions and/or voids"
    )
    target_cell_range: Tuple[int, int] = (200000, 2000000)
    # 区域划分规则：与区域名做正则匹配的规则列表。
    # 命中任一 fluid 规则 → fluid；否则 → solid。由配置给出，代码不含任何具体区域名。
    fluid_region_rules: List[str] = field(default_factory=list)
    # 边界类型自动分配说明（自然语言，供运行时判断是否需要覆盖）
    boundary_type_note: str = (
        "<自然语言：说明命名边界与类型的关系，例如 名称含 inlet 的面是速度入口，"
        "outlet 是压力出口；默认依赖 Fluent 的 *inlet*/*outlet* 名字自动分配>"
    )


@dataclass
class SolverConfig:
    """求解阶段配置（工程参数；物理由 physics 自然语言描述）。"""
    precision: str = "double"
    processors: int = 4
    memory_budget_gb: float = 10.0     # 本机内存预算（守卫用，按机器填）
    max_iterations: int = 400
    batch_size: int = 200
    continuity_threshold: float = 5e-3  # 连续性残差判据（通用管道参数）
    init_note: str = "<自然语言：初始化方式，例如 混合初始化 hybrid initialization>"
    convergence_note: str = (
        "<自然语言：收敛判据与策略，例如 连续性<5e-3 判收敛；若平台震荡不收敛，"
        "按运行时指令决定是否停止>"
    )


@dataclass
class PhysicsConfig:
    """物理设置——全部自然语言占位，由运行时解释器翻译为 PyFluent 调用。"""
    models: str = "<自然语言：湍流模型、能量方程、多相/辐射等模型选择>"
    materials: str = "<自然语言：材料种类与物性数值，如 水 998.2/4182/0.6/0.001003>"
    boundary_conditions: str = "<自然语言：各边界的类型与数值，如 冷入口 0.5m/s 25C>"
    methods_and_controls: str = (
        "<自然语言：压力-速度耦合算法、离散格式、松弛因子、初始化方式>"
    )
    monitors: str = "<自然语言：需要监测的物理量，如 进出口压降、质量流量、出口温度>"


@dataclass
class PostConfig:
    """后处理配置——需求以自然语言条目给出。"""
    contours: List[str] = field(default_factory=list)   # 云图需求条目
    sections: List[str] = field(default_factory=list)   # 截面需求条目
    xy_plots: List[str] = field(default_factory=list)   # XY 曲线需求条目
    reports: List[str] = field(default_factory=list)    # 工程量提取需求条目（如出口温度）
    stage_dir_no_space: str = ""   # TUI 存图暂存目录：必须无空格（血泪教训）


@dataclass
class FlowConfig:
    """总配置。"""
    name: str = "cfd-run"
    output_root: str = ""
    mesh: MeshConfig = field(default_factory=MeshConfig)
    solver: SolverConfig = field(default_factory=SolverConfig)
    physics: PhysicsConfig = field(default_factory=PhysicsConfig)
    post: PostConfig = field(default_factory=PostConfig)

    @classmethod
    def from_file(cls, path: str) -> "FlowConfig":
        with open(path, "r", encoding="utf-8") as fh:
            raw: dict = json.load(fh)
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: dict) -> "FlowConfig":
        def get(section: str, key: str, default: Any) -> Any:
            return raw.get(section, {}).get(key, default)

        mesh_raw = raw.get("mesh", {})
        solver_raw = raw.get("solver", {})
        physics_raw = raw.get("physics", {})
        post_raw = raw.get("post", {})

        mesh = MeshConfig(
            geometry_file=get("mesh", "geometry_file", ""),
            length_unit=mesh_raw.get("length_unit", "mm"),
            min_size=mesh_raw.get("min_size", 2.0),
            max_size=mesh_raw.get("max_size", 40.0),
            growth_rate=mesh_raw.get("growth_rate", 1.2),
            volume_fill=mesh_raw.get("volume_fill", "poly-hexcore"),
            describe_geometry=mesh_raw.get(
                "describe_geometry",
                "The geometry consists of both fluid and solid regions and/or voids",
            ),
            target_cell_range=tuple(mesh_raw.get("target_cell_range", [200000, 2000000])),
            fluid_region_rules=list(mesh_raw.get("fluid_region_rules", [])),
            boundary_type_note=mesh_raw.get("boundary_type_note", ""),
        )
        solver = SolverConfig(
            precision=solver_raw.get("precision", "double"),
            processors=solver_raw.get("processors", 4),
            memory_budget_gb=solver_raw.get("memory_budget_gb", 10.0),
            max_iterations=solver_raw.get("max_iterations", 400),
            batch_size=solver_raw.get("batch_size", 200),
            continuity_threshold=solver_raw.get("continuity_threshold", 5e-3),
            init_note=solver_raw.get("init_note", ""),
            convergence_note=solver_raw.get("convergence_note", ""),
        )
        physics = PhysicsConfig(
            models=physics_raw.get("models", ""),
            materials=physics_raw.get("materials", ""),
            boundary_conditions=physics_raw.get("boundary_conditions", ""),
            methods_and_controls=physics_raw.get("methods_and_controls", ""),
            monitors=physics_raw.get("monitors", ""),
        )
        post = PostConfig(
            contours=list(post_raw.get("contours", [])),
            sections=list(post_raw.get("sections", [])),
            xy_plots=list(post_raw.get("xy_plots", [])),
            reports=list(post_raw.get("reports", [])),
            stage_dir_no_space=post_raw.get("stage_dir_no_space", ""),
        )
        return cls(
            name=raw.get("name", "cfd-run"),
            output_root=raw.get("output_root", ""),
            mesh=mesh,
            solver=solver,
            physics=physics,
            post=post,
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "output_root": self.output_root,
            "mesh": {
                "geometry_file": self.mesh.geometry_file,
                "length_unit": self.mesh.length_unit,
                "min_size": self.mesh.min_size,
                "max_size": self.mesh.max_size,
                "growth_rate": self.mesh.growth_rate,
                "volume_fill": self.mesh.volume_fill,
                "describe_geometry": self.mesh.describe_geometry,
                "target_cell_range": list(self.mesh.target_cell_range),
                "fluid_region_rules": self.mesh.fluid_region_rules,
                "boundary_type_note": self.mesh.boundary_type_note,
            },
            "solver": {
                "precision": self.solver.precision,
                "processors": self.solver.processors,
                "memory_budget_gb": self.solver.memory_budget_gb,
                "max_iterations": self.solver.max_iterations,
                "batch_size": self.solver.batch_size,
                "continuity_threshold": self.solver.continuity_threshold,
                "init_note": self.solver.init_note,
                "convergence_note": self.solver.convergence_note,
            },
            "physics": {
                "models": self.physics.models,
                "materials": self.physics.materials,
                "boundary_conditions": self.physics.boundary_conditions,
                "methods_and_controls": self.physics.methods_and_controls,
                "monitors": self.physics.monitors,
            },
            "post": {
                "contours": self.post.contours,
                "sections": self.post.sections,
                "xy_plots": self.post.xy_plots,
                "reports": self.post.reports,
                "stage_dir_no_space": self.post.stage_dir_no_space,
            },
        }
