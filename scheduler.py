# -*- coding: utf-8 -*-
"""
scheduler.py — 流程调度器。

把网格→求解→后处理三个阶段串成一条带检查点的流水线：
  - 每个阶段只做机械的、与项目无关的动作（会话管理、两段式网格、落盘顺序、暂存目录等）；
  - 所有物理动作经 PhysicsInterpreter 注入；
  - 每个阶段执行前跑检查点（lessons.py），失败即阻断并给出人类可读原因；
  - 阶段结果与产物路径全部登记，最终输出一份汇总报告。
"""
from __future__ import annotations

import json
import os
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import lessons
from .config import FlowConfig
from .physics_adapter import NullInterpreter, PhysicsInterpreter


@dataclass
class StageResult:
    stage: str
    ok: bool
    message: str
    artifacts: List[str] = field(default_factory=list)
    traceback: str = ""

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "ok": self.ok,
            "message": self.message,
            "artifacts": self.artifacts,
            "traceback": self.traceback,
        }


@dataclass
class RunContext:
    """阶段间共享的上下文。"""
    config: FlowConfig
    interpreter: PhysicsInterpreter
    fluent_factory: Optional[Callable] = None   # 注入式工厂：便于离线测试
    results: Dict[str, Any] = field(default_factory=dict)
    log: List[str] = field(default_factory=list)

    def out(self, sub: str) -> str:
        p = os.path.join(self.config.output_root, sub)
        os.makedirs(p, exist_ok=True)
        return p


class Scheduler:
    """CFD 流程调度器。"""

    def __init__(
        self,
        config: FlowConfig,
        interpreter: Optional[PhysicsInterpreter] = None,
        fluent_factory: Optional[Callable] = None,
    ) -> None:
        self.config = config
        self.interpreter = interpreter if interpreter is not None else NullInterpreter()
        self.fluent_factory = fluent_factory
        self.ctx = RunContext(
            config=config,
            interpreter=self.interpreter,
            fluent_factory=fluent_factory,
        )
        self._stages: Dict[str, Callable[[RunContext], StageResult]] = {}

    def register(self, name: str, fn: Callable[[RunContext], StageResult]) -> None:
        self._stages[name] = fn

    def load_builtin_stages(self) -> None:
        from . import stages_meshing, stages_post, stages_solver

        self.register("mesh", stages_meshing.stage_meshing)
        self.register("solve", stages_solver.stage_solver)
        self.register("post", stages_post.stage_post)

    def run(self, stages: Optional[List[str]] = None) -> Dict[str, StageResult]:
        """按顺序执行阶段；前一阶段失败则阻断后续阶段（fail-fast）。"""
        if not self._stages:
            self.load_builtin_stages()
        names = list(stages) if stages else list(self._stages.keys())
        outcomes: Dict[str, StageResult] = {}
        for name in names:
            if outcomes and not outcomes[list(outcomes)[-1]].ok:
                outcomes[name] = StageResult(
                    stage=name, ok=False, message="前置阶段失败，已阻断"
                )
                break
            fn = self._stages[name]
            try:
                r = fn(self.ctx)
            except Exception as exc:
                r = StageResult(
                    stage=name, ok=False,
                    message=f"{type(exc).__name__}: {exc}",
                    traceback=traceback.format_exc(),
                )
            outcomes[name] = r
            self.ctx.log.append(f"[{name}] ok={r.ok} {r.message}")
        self.write_report(outcomes)
        return outcomes

    def write_report(self, outcomes: Dict[str, StageResult], path: Optional[str] = None) -> str:
        p = path or os.path.join(
            self.ctx.out(""), "scheduler_report.json"
        )
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "project": self.config.name,
                    "output_root": self.config.output_root,
                    "stages": {k: v.to_dict() for k, v in outcomes.items()},
                },
                fh, ensure_ascii=False, indent=2,
            )
        return p
