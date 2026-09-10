# -*- coding: utf-8 -*-
"""
cfd_scheduler — 把 CFD 自动化血泪教训固化下来的流程调度器。

用法速览：
    from cfd_scheduler import Scheduler, FlowConfig
    cfg = FlowConfig.from_file("config.json")
    sch = Scheduler(cfg, interpreter=my_interpreter)
    results = sch.run(["mesh", "solve", "post"])
"""
from .config import FlowConfig, MeshConfig, PhysicsConfig, PostConfig, SolverConfig
from .physics_adapter import (
    NullInterpreter,
    PhysicsInterpreter,
    adjacent_cell_zone,
    boundary_groups,
    fluid_zones,
    solid_zones,
)
from .scheduler import RunContext, Scheduler, StageResult
from . import lessons

__all__ = [
    "Scheduler", "RunContext", "StageResult",
    "FlowConfig", "MeshConfig", "SolverConfig", "PhysicsConfig", "PostConfig",
    "PhysicsInterpreter", "NullInterpreter",
    "fluid_zones", "solid_zones", "boundary_groups", "adjacent_cell_zone",
    "lessons",
]
