
# robot_vs

本仓库实现了一个基于 ROS1 的多机器人红蓝对抗系统。

系统整体由三大核心子系统组成：

1. **裁判系统（Referee）**
2. **决策系统（LLM / MAS）**
3. **执行系统（Car Agent + Skill）**

其中决策系统支持两种实现方式：

- ✅ 大模型集中式决策（LLM Manager）
- ✅ 分层多智能体决策（MAS：Leader + CarAgent）

---

# 一、系统整体分层结构

```
┌────────────────────────────────────┐
│            RefereeNode             │
│  命中判定 / HP管理 / 视野计算       │
└────────────────────────────────────┘
                │
                ▼
┌────────────────────────────────────┐
│          决策系统 (二选一)          │
│                                    │
│  A. LLM Manager 模式              │
│  B. MAS 分层多智能体模式           │
└────────────────────────────────────┘
                │
                ▼
┌────────────────────────────────────┐
│        Car Agent 执行系统           │
│  task_engine + skill_manager +     │
│  GoTo / Stop / Attack 等技能       │
└────────────────────────────────────┘
```

---

# 二、目录结构说明（程序层级）

```
robot_vs/
│
├── scripts/
│   ├── manager/            # ✅ 单模型决策系统（LLM Manager）
│   ├── MAS/                # ✅ 分层多智能体决策系统
│   ├── car/                # ✅ 执行系统（Car Agent + Skill）
│   ├── visualization/      # ✅ 可视化系统
│   ├── mowen/              # ✅ 真机底盘驱动
│
├── config/                 # 参数配置文件
├── launch/                 # 启动文件
├── msg/                    # 自定义消息
├── worlds/                 # Gazebo 世界
├── maps/                   # 地图
```

---

# 三、裁判系统（Referee 层）

## 位置

```
scripts/manager/referee_node.py
```

## 职责

- 订阅所有小车 `/robot_state`
- 订阅所有小车 `/fire_event`
- 执行射线命中检测
- 扣减 HP
- 判断死亡
- 计算视野（FOV + 距离 + 地图遮挡）
- 发布：
  - `/referee/macro_state`
  - `/red_manager/enemy_state`
  - `/blue_manager/enemy_state`

## 作用

裁判系统是整个对抗系统的“物理规则层”，  
决策系统不直接决定命中，而由裁判统一管理。

---

# 四、决策系统一：大模型集中式决策（LLM Manager）

## 结构

```
scripts/manager/
│
├── manager_node.py
├── global_observer.py
├── battle_state_formatter.py
├── llm_client.py
└── task_dispatcher.py
```

---

## 决策流程

### 1️⃣ GlobalObserver

收集：

```
/<robot_ns>/robot_state
/referee/macro_state
/<manager_ns>/enemy_state
```

生成统一战场状态字典。

---

### 2️⃣ BattleStateFormatter

将状态转换为 LLM 输入结构：

```json
{
  "battle_state": {...},
  "robot_ids": [...]
}
```

---

### 3️⃣ LLMClient

通过 HTTP 调用：

```
POST http://127.0.0.1:8001/plan
```

获取所有车辆的任务。

若失败 → 规则兜底。

---

### 4️⃣ TaskDispatcher

发布：

```
/robot_x/task_cmd
```

消息类型：

```
TaskCommand.msg
```

---

## 适用场景

- 多车统一策略
- Prompt 实验
- 简单协同测试
- 小规模对抗

---

# 五、决策系统二：分层多智能体（MAS）

## 结构

```
scripts/MAS/
│
├── agents/
│   ├── leader_agent.py
│   ├── car_agent.py
│
├── memory/
│   ├── stm.py
│   ├── ltm.py
│
├── llm_server.py
└── mas_manager.py
```

---

## 分层结构

```
LeaderAgent（慢周期）
        │
        ▼
LeaderOrder（战略文本）
        │
        ▼
CarAgent × N（快周期）
        │
        ▼
单车动作 JSON
```

---

## LeaderAgent

- 输入：全局状态
- 使用：STM（短期记忆）
- 使用：LTM（长期记忆）
- 输出：战略文本（不输出坐标）

---

## CarAgent

- 输入：
  - LeaderOrder
  - 当前车状态
  - 全局上下文
- 输出：
  - 单车动作 JSON
- 支持：
  - fallback
  - 上次任务复用
  - 并发调用

---

## STM / LTM

### STM

- 最近 N 个状态窗口
- 提供趋势信息

### LTM

- JSONL 持久化
- 保存战术经验

---

## MAS Server

文件：

```
scripts/MAS/llm_server.py
```

监听两个端口：

- red：8001
- blue：8002

Manager 无需修改，只需指向该端口。

---

## 适用场景

- 分层 AI 实验
- 多智能体协同
- 战术演化研究
- 并发决策研究

---

# 六、执行系统（Car Agent + Skill）

## 结构

```
scripts/car/
│
├── car_node.py
├── task_engine.py
├── skill_manager.py
└── skills/
    ├── goto_skill.py
    ├── stop_skill.py
    ├── attack_skill.py
    └── rotate_skill.py
```

---

## 执行流程

```
TaskCommand
    ↓
TaskEngine.accept_task()
    ↓
SkillManager.make_skill()
    ↓
具体 Skill 执行
```

---

## 技能列表

| Skill | 作用 |
|--------|------|
| GoToSkill | 发布导航目标 |
| StopSkill | 刹车 |
| AttackSkill | 转向 + fire_event |
| RotateSkill | 原地旋转 |

---

# 七、数据闭环

## Manager → Car

```
TaskCommand
```

## Car → Manager

```
RobotState
```

## Referee → Manager

```
BattleMacroState
VisibleEnemies
```

---

# 八、快速运行

## 编译

```bash
cd ~/catkin_ws/src
git clone https://github.com/Xqrion/robot_vs.git
cd ~/catkin_ws
catkin_make
source devel/setup.bash
```

---

## 仿真运行

```bash
roslaunch robot_vs simulation/2v2vs.launch
```

---

## 启动决策服务（二选一）

### ✅ LLM Manager

```bash
bash config/AI/start_llm_services.sh
```

### ✅ MAS

```bash
bash config/AI/start_mas_services.sh
```

---

# 九、项目状态

| 模块 | 状态 |
|------|------|
| 裁判系统 | ✅ 完整 |
| 执行系统 | ✅ 完整 |
| LLM 决策系统 | ✅ 完整 |
| MAS 分层系统 | ✅ 完整 |
| STM / LTM | ✅ 完整 |
| 真机对抗 | ✅ 可运行 |
| 大规模实战调优 | 🚧 进行中 |
```
