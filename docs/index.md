---
layout: default
title: 基于 DeepSeek Harness 和 PyFluent 的 CFD 求解 Agent
---

# 基于 DeepSeek Harness 和 PyFluent 的 CFD 求解 Agent

**用自然语言指挥 CFD：从几何到结果评价的全流程自动化。**

本项目把一次真实的管壳式换热器 CFD 实战（SpaceClaim 几何 → Fluent Meshing 水密工作流
→ poly-hexcore 体网格 → 求解器设置 → 迭代求解 → 后处理）中踩过的坑，
固化成一套**可复用、可验证、可迁移**的自动化流水线。

[查看源码仓库](https://github.com/JamesDa-zhang/James-Workbench) ·
[核心原理](principles.html) ·
[操作手册](playbook.html)

---

## 核心特性

### 1. 零物理硬编码
代码里没有任何具体物理数值或模型名（没有"水密度 998"、没有"入口速度 0.5"、没有"k-epsilon"）。
湍流模型、材料物性、边界数值全部以**自然语言**写在 `config.json`，运行时由解释器翻译为 PyFluent 调用。
**换新案例不需要改一行调度器代码。**

### 2. 九条工程检查点（血泪教训固化）
每条来自真实失败，对应一个可执行校验函数，失败即阻断，绝不带病运行：

| ID | 教训 | 守卫机制 |
|---|---|---|
| L1 | 区域类型"数量对但位置错" | 逐名称配对校验 |
| L2 | `set_state` 内部会执行命令 | 禁止重复 Execute |
| L3 | 单元数超内存 → 迭代即崩 | 单元数×3.2KB×1.5 ≤ 预算 |
| L4 | TUI 控制台脏状态毒化后续操作 | 分步交互 + 两段式会话隔离 |
| L5 | TUI 路径含空格被截断 | 无空格暂存目录 |
| L6 | CAD 文件被锁导入失败 | 复制后导入 |
| L7 | 大 case+data 单次写 → 连接重置 | 先 data 后 case + 重试 |
| L8 | 混合初始化表格被误认成残差（假收敛） | 只认 8 列残差行 |
| L9 | 网格量级失控 | 目标区间配置化 + 落盘校验 |

### 3. 三阶段调度器（fail-fast）
网格（两段式会话隔离）→ 求解（内存检查点 + 分批迭代 + 残差解析）→ 后处理（渲染 + 曲线 + 报告），
前一阶段失败自动阻断后续阶段，并写出结构化报告。

### 4. 物理解释器协议
`PhysicsInterpreter` 定义 6 个方法，把自然语言（如"冷入口 0.5m/s 25°C"）翻译成 PyFluent settings 调用；
不提供解释器时退化为 `NullInterpreter`（只记录不执行），保证机械部分仍可离线干跑测试。

---

## 架构

```
┌──────────────────────────────────────────────────────┐
│ DeepSeek Harness（Agent 决策层）                      │
└───────────────────────┬──────────────────────────────┘
                        │ 命令编排
┌───────────────────────▼──────────────────────────────┐
│ agent_playbook：0→1→2→3 正确路径（auto_flow 一键入口）│
└───────────────────────┬──────────────────────────────┘
                        │ 复用调度器
┌───────────────────────▼──────────────────────────────┐
│ cfd_scheduler：三阶段流水线 + L1~L9 检查点守卫        │
│ config.json（自然语言物理）→ 解释器 → PyFluent 调用   │
└───────────────────────┬──────────────────────────────┘
                        │ launch_fluent() / gRPC
┌───────────────────────▼──────────────────────────────┐
│ PyFluent 0.42 → Ansys Fluent 2024 R2                 │
│ meshing 模式：水密工作流 → poly-hexcore 体网格        │
│ solver 模式：读网格 → 物理注入 → 迭代 → 后处理        │
└──────────────────────────────────────────────────────┘
```

---

## 实测验证

| 验证项 | 结果 |
|---|---|
| 离线测试 `test_offline.py` | **PASS 19 / 19** |
| Playbook 离线测试 | **PASS 7 / 7** |
| 环境与连接检查 | `PYFLUENT_OK 0.42.0` + `FLUENT_FOUND v242` |
| 真实连接探针 | **LAUNCH_OK — Ansys Fluent 2024 R2** |
| 实战案例 | 管壳式换热器 ~60 万单元，400 步迭代，4 张云图 + 轴向温度曲线 + 残差曲线 |

---

## 快速开始

```bash
pip install -r cfd_scheduler/requirements.txt

# ① 环境检查（不启动 Fluent）
cd cfd_scheduler/agent_playbook && python stage0_environment.py

# ② 离线测试（不启动 Fluent）
cd .. && python test_offline.py

# ③ 连接探针（真实启动一次会话，验证 license 与 gRPC 通路）
cd agent_playbook && python stage0_environment.py --probe

# ④ 一键跑完整流程
python auto_flow.py --geometry "D:/work/model.scdoc" --output "D:/work/out" --config config.json
```

**环境要求**：Python 3.10+ · `ansys-fluent-core==0.42.*` · Ansys Fluent 2024 R2+ · 有效 license

---

## 文档

- [核心工作原理](principles.html) — 连接机制、两段式网格、检查点触发点、解释器协议、数据产物链
- [Agent 操作手册](playbook.html) — 0→1→2→3 正确路径与决策规则
- [项目 README](readme.html) — 目录结构、血泪教训清单、成功路径

---

*由 DeepSeek Harness 会话沉淀 · 源码托管于 [GitHub](https://github.com/JamesDa-zhang/James-Workbench)*
