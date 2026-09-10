# 正确的指导（Agent Playbook）

> 本文件是"正确路径"的蒸馏：新 AI 拿到本文件夹后，**先读本文件，再执行命令**，
> 即可按已验证的路径自动完成 CFD 全流程，无需重新试错。
> 背景与"为什么"见工作区根目录 CFD_PROCESS_LOG.md；本文件只给"怎么做"。

## 0. 一句话总纲

python auto_flow.py --geometry <用户提供的 .scdoc> [--config 可选] [--interpreter 可选]
它自动完成：环境与连接检查 → 几何校验 → 网格（两段式）→ 求解 → 后处理 → 结果评价。

---

## 一、部署与连接：让 Agent 能用 PyFluent 操控本机 Fluent

**检查清单（stage0_environment.py 会自动做，也可人工核）**

1. Python 3.10+，且 pip 已装 ansys-fluent-core（当前验证版本 0.42.*）：
   pip install ansys-fluent-core==0.42.*
2. 本机安装 Fluent 2024 R2+（PyFluent 0.42 只支持 24.2/25.1/25.2，不支持 2022 R1）；
   安装目录需能被环境变量 AWP_ROOT242（或 251）指到，或在标准路径下。
3. license 有效（1055@localhost 或单位服务器）。

**执行**

    python stage0_environment.py --probe

预期输出：PYFLUENT_OK / FLUENT_FOUND ... / LAUNCH_OK, version: Ansys Fluent 2024 R2。

**决策规则（遇到问题怎么处理）**

- "compatible installation" 找不到 → 检查 AWP_ROOT242；没有就新建环境变量指向 v242 安装根目录。
- license 报错 → 停下，请用户修复 license 后重跑（不要尝试绕过许可）。
- 连接成功后**不要**长时间占着会话做实验；先退出，正式流程由 auto_flow 管理。

---

## 二、几何输入：提醒用户提供 SpaceClaim 前处理文件

**必须向用户索要的输入**（stage1_input.py 会自动提醒）：

1. 一个 SpaceClaim 前处理后的文件（.scdoc 或 .pmdb），要求：
   - **已抽取流体域**（必要时包含固体域）；
   - **带命名选择**（named selections）：每个入口/出口/壁面/固体都有名字，
     这是后面边界条件与区域类型自动化的前提。
2. 单位（默认 mm；不确定时先用 mm，让"描述几何"步骤报告尺寸后复核）。

**执行**

    python stage1_input.py --geometry "D:/work/model.scdoc"

没有提供路径时，程序会打印提醒语并退出（退出码 2）——AI 应把提醒语转达给用户。

**决策规则**

- 文件不存在/扩展名不对 → 请用户重新导出。
- 命名选择为空（导入探针可查）→ 请用户回 SpaceClaim 补命名，再继续。

---

## 三、正确路径：网格 → 求解设置 → 数值模拟 → 后处理

**顺序是固定的（stage2_run.py / auto_flow.py 已内置，勿打乱）**

   网格：
     1. meshing 模式 + ui_mode=hidden_gui + graphics_driver=dx11 + 双精度
     2. watertight 工作流；几何复制到临时文件再导入（防 CAD 锁）
     3. 曲率尺寸函数：界面 min 加密、域内 max 粗化（数值来自 config）
     4. 面网格 → 描述几何（选项来自 config）→ 边界自动分配
     5. 区域类型：按 config 的 fluid_region_rules 正则判定，TUI 分步修改（对象名→区域名→fluid→空行）
        → 逐名称精确校验 → save_workflow
     6. 换新会话 load_workflow → 体网格 → datamodel WriteCase 落盘
   求解：
     7. 读网格 → 内存检查点（单元数×3.2KB×1.5 ≤ 预算，超则粗化 max_size）
     8. 物理全部经解释器注入（模型/材料/边界/方法/监测量，自然语言→settings 调用）
     9. 分批迭代（批次/上限来自 config）；残差按 8 列解析写 CSV；与阈值比较
    10. 先 write_data 再 write_case（分开写、带重试）
   后处理：
    11. dx11 驱动会话读 case+data；云图/截面经 PostHelpers；TUI 存图走无空格暂存
    12. 残差曲线 matplotlib 化；报告类提取失败自动写手动说明

**执行**

    python auto_flow.py --geometry "D:/work/model.scdoc" --output "D:/work/out" [--config config.json]

**关键决策规则**

- fluid_region_rules 必须是真实正则（先探针读命名选择再填）；占位符状态会被程序拒绝。
- 网格量级不在 target_cell_range → 调整 min/max_size 重划，不要硬上。
- 连续性平台震荡不收敛（其余方程已收敛）→ 按用户指令决定停止或调整边界；不要无脑加迭代。
- 运行期间提醒用户不要打开 Fluent GUI / 不要移动几何文件（进程会被杀、文件会被锁）。

---

## 四、结果分析与评价

**执行**

    python stage3_evaluate.py --output "D:/work/out"

自动生成 EVALUATION.md，评价四个维度：

1. 收敛性：读 residuals.csv → 末值连续性 vs 阈值；各方程趋势；给出"收敛/未收敛+原因类别"结论。
2. 网格量级：单元数是否落在目标区间（超出=内存风险提示）。
3. 产物完整性：case/data/图片/CSV 是否齐全。
4. 物理合理性：transcript 中回流（Reversed flow）等警告自动检索并提示人工复核。

**评价报告是给用户看的结论页**：包含"能否用于工程判断"的明确说法与下一步建议。

---

## 五、API 速查（正确写法，勿再试错）

| 需求 | 正确写法 |
|---|---|
| 启动 meshing/solver | launch_fluent(mode=..., precision=..., ui_mode="hidden_gui", graphics_driver="dx11", start_transcript=True) |
| 读 case | settings.file.read_case(file_name=路径) |
| 迭代 | settings.solution.run_calculation.iterate(iter_count=N) |
| 耦合算法 | solution.methods.p_v_coupling.flow_scheme = "Coupled" |
| 混合初始化 | solution.initialization.hybrid_initialize() |
| 材料 | materials.fluid.create(名) 后 mat.density.value = 数值 |
| 速度入口 | bc.momentum.vmag.value / bc.thermal.temperature.value |
| 云图 | results.graphics.contour[name]={} → field / surfaces_list → display |
| 截面 | results.surfaces.plane_surface.create(name) + method="yz-plane" + x=坐标 |
| 存图 | tui.display.re_render() + tui.display.save_picture(无空格路径) |
| 网格落盘 | meshing.meshing.File.WriteCase(FileName=...)（datamodel，不走 TUI） |
| 工作流存档/加载 | wf.save_workflow(.wft) / meshing.load_workflow(.wft) |
| 区域改类型 | TUI /objects/volumetric-regions/change-type 分步交互（对象名→区域名→fluid→空行） |
| 参数命名 | 工作流参数一律蛇形（cfd_surface_mesh_controls.min_size） |

## 六、铁律（不可违反）

1. 代码里不写物理数值与模型名——全部从 config/解释器注入。
2. set_state 之后严禁再 Execute（会覆盖）。
3. TUI 路径必须无空格。
4. 长任务前先跑检查点（内存/区域/路径）。
5. 关键产物立即落盘，先 data 后 case。
6. 不收敛时按规则停止，不擅自无限加迭代。
