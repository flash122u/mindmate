# Step 2：人格系统与防御机制

## 目标

完善人格核心，加入防御机制和关系演进系统。

## 需新增/修改的文件

### 1. personality/defense.py — 防御机制
- 解析用户消息，判断是否触发"雷区"
- 触发后注入防御指令（回避/撒谎/转移话题）
- 在 AgentLoop 的 _build_context 之前执行

### 2. personality/relationship.py — 关系阶段管理
- 跟踪关系阶段：初识 → 朋友 → 信赖
- 根据对话情感倾向自动演进
- 影响 Agent 的亲密程度和回复风格

### 3. 修改 personality/soul.py
- 增加 `get_defense_rules()` 方法
- 增加 `update_relationship_stage()` 方法

### 4. 修改 agent/loop.py
- 在 _process_message 中插入 Defense 检查
- 在 _build_context 中注入关系阶段信息

## 验收标准

- 问"你是不是机器人？"时触发防御
- 连续友好对话后关系阶段演进
- 防御机制不影响正常对话
