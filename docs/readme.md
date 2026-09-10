---
layout: default
title: 项目 README
---

# cfd_scheduler — CFD 自动化流程调度器（血泪教训固化版）

> **新 AI 想直接跑流程？请先看 agent_playbook/ 文件夹**（AGENT_GUIDE.md + auto_flow.py 一键入口）：
> 那是"正确路径"的蒸馏，按它执行无需重新试错。本 README 与 lessons.py 是它的底层机制说明。

这个项目把一次完整的 CFD 自动化实战（SpaceClaim 几何 → Fluent Meshing 水密工作流
→ poly-hexcore 体网格 → 求解器设置 → 迭代 → 后处理）中踩过的坑，固化为：

1. **检查点守卫**（lessons.py）：每个血泪教训对应一个可执行的校验函数，失败即阻断；
2. **三阶段调度器**（scheduler.py + stages_*.py）：网格 → 求解 → 后处理，fail-fast；
3. **顶层轻量级配置**（config.example.json）：一切项目相关量从外部传入；
4. **物理解释器协议**（physics_adapter.py）：物理全部以自然语言占位符进入，运行时翻译。

## 核心原则（零物理硬编码）

- 代码里**没有任何**具体物理数值或模型名（没有"水密度 998"、没有"入口速度 0.5"、
  没有"k-epsilon"、没有具体区域名）；
- 湍流模型、松弛因子、监测物理量等，全部以**自然语言占位符**放在顶层配置的
  physics / post 段，由运行时解释器（AI 或项目专属实现）翻译为 PyFluent 调用；
- 数值只出现在 config.json 中：网格尺寸、单元数目标区间、内存预算、迭代批次、
  连续性阈值——这些是通用工程参数，不属于"特定模型"。

## 使用方式

```bash
python run_flow.py --config config.json --stages mesh,solve,post --interpreter my_interpreter.py
```

- `config.json`：按 config.example.json 模板填写（物理条目保持自然语言描述）；
- `my_interpreter.py`：实现 `build_interpreter()` 返回 PhysicsInterpreter 实例，
  用 physics_adapter 里的访问器（fluid_zones / boundary_groups / adjacent_cell_zone …）
  把自然语言翻译为 settings 调用。不提供时退化为 NullInterpreter（只记录不执行）。

## 血泪教训清单（lessons.py 中的 L1~L9）

| ID | 教训 | 守卫/机制 |
|----|------|-----------|
| L1 | 区域类型"数量对但位置错"（如 fins 被设成 fluid） | check_region_type_pairs 逐名称配对校验 |
| L2 | set_state 内部会执行命令，再 Execute 会覆盖已设类型 | 代码约定：set_state 后严禁重复 Execute |
| L3 | 单元数×精度超内存预算 → 迭代即崩（MPI 心跳超时） | check_memory_estimate，超预算阻断 |
| L4 | TUI 控制台脏状态随机毒化后续操作 | 分步交互+空行收尾；网格阶段两段式（会话A存档→会话B干净加载） |
| L5 | TUI 路径含空格被截断 | check_tui_path_no_space + 无空格暂存目录 |
| L6 | CAD 文件被 SpaceClaim 锁定 → 导入失败 | 复制后导入 |
| L7 | case+data 单次大写入 → gRPC 连接重置丢结果 | 先 data 后 case，分开写，带重试 |
| L8 | 混合初始化表格被误认成求解残差（假收敛） | parse_residual_rows 只认 8 列残差行 |
| L9 | 网格量级失控 | target_cell_range 配置化，落盘后校验 |

## 成功路径（未来 AI 可直接照抄）

1. **网格**：meshing 模式 + dx11 驱动 → watertight 工作流 → 复制导入 → 曲率尺寸
   （界面 min 加密 / 域内 max 粗化）→ 面网格 → describe（选项来自配置）→
   边界自动分配 → 区域类型按 fluid 规则正则判定、TUI 分步修改 → **逐名称校验** →
   save_workflow → **换新会话 load_workflow**（干净控制台）→ 体网格 →
   **datamodel WriteCase** 落盘（不经 TUI）；
2. **求解**：读网格 → **内存检查点** → 解释器注入物理（模型/材料/边界/方法/监测）→
   分批迭代 → 残差 8 列解析 + 阈值判定（阈值来自配置）→ **先 data 后 case** 落盘；
3. **后处理**：dx11 驱动 → 云图/截面经 PostHelpers（机械）由解释器驱动 →
   TUI 存图走无空格暂存 → 残差曲线 matplotlib → 报告类提取失败时写手动说明。

## 目录结构

```
cfd_scheduler/
├── README.md              # 本文件：经验包
├── config.example.json    # 顶层配置模板（NL 占位符）
├── run_flow.py            # 入口
├── test_offline.py        # 离线测试（不启动 Fluent）
└── cfd_scheduler/
    ├── config.py          # 配置模型与加载
    ├── lessons.py         # L1~L9 检查点守卫 + 教训注册表
    ├── physics_adapter.py # 解释器协议 + 通用访问器（零物理值）
    ├── scheduler.py       # 调度器：注册/执行/fail-fast/报告
    ├── stages_meshing.py  # 网格阶段（两段式）
    ├── stages_solver.py   # 求解阶段
    └── stages_post.py     # 后处理阶段
```
