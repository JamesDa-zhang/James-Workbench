# James-Workbench

工程自动化工作台：把「人机协作完成真实工程任务」过程中踩过的坑，
固化成可复用、可验证、可迁移的代码与文档。

## 项目索引

| 项目 | 说明 | 状态 |
|---|---|---|
| [cfd_scheduler](./cfd_scheduler) | 基于 DeepSeek Harness + PyFluent 的 CFD 求解 Agent：自然语言配置驱动 几何/网格/求解/后处理 全流程自动化，内置血泪教训检查点 | 可用（离线测试 19/19 通过） |

---

## cfd_scheduler 快速开始

用自然语言指挥 CFD：DeepSeek Harness 中的 Agent 负责理解与编排，
PyFluent 负责驱动本机 Ansys Fluent，`cfd_scheduler` 负责带检查点的三阶段流水线调度。

```bash
pip install -r cfd_scheduler/requirements.txt

# ① 环境检查（不启动 Fluent）
cd cfd_scheduler/agent_playbook && python stage0_environment.py

# ② 离线测试（不启动 Fluent）
cd .. && python test_offline.py

# ③ 连接探针（真实启动一次 Fluent 会话，验证 license 与 gRPC 通路）
cd agent_playbook && python stage0_environment.py --probe

# ④ 一键跑完整流程
python auto_flow.py --geometry "D:/work/model.scdoc" --output "D:/work/out" --config config.json
```

详细原理见 [`cfd_scheduler/工作原理.md`](./cfd_scheduler/工作原理.md)；
操作路径见 [`cfd_scheduler/agent_playbook/AGENT_GUIDE.md`](./cfd_scheduler/agent_playbook/AGENT_GUIDE.md)。

## 设计原则

1. **零物理硬编码**：湍流模型、材料物性、边界数值全部以自然语言写在 `config.json`，
   运行时由解释器翻译为 PyFluent 调用；代码里只保留通用工程参数。
2. **检查点守卫**：每条真实教训对应一个可执行校验（内存预算、区域逐名称配对、
   TUI 路径空格、残差 8 列解析……），失败即阻断，绝不带病运行。
3. **机械与物理分离**：机械动作（会话管理、两段式网格、落盘顺序）固化在调度器；
   物理动作经解释器协议注入——换新案例不必改调度器代码。

## 环境要求

- Python 3.10+
- `ansys-fluent-core==0.42.*`（对应 Fluent 24.2 / 25.1 / 25.2）
- 本机安装 Ansys Fluent 2024 R2+，`AWP_ROOT242` 指向安装根目录
- 有效 license（本地或单位许可服务器）
