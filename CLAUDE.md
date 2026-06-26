# MindMate 项目记忆文件

## 启动协议

新轮启动时先执行以下恢复流程：

```
1. 读 progress.json（如存在）
   - 不存在 → 从 step-2 生成的任务列表初始化
   - 存在 → 找第一个 status=="pending" 的任务 ID
2. 读对应 plan 文件 → 获取任务详情
3. git log --oneline -5 → 了解最近变更
4. 读任务涉及的源文件 → 了解当前代码状态
5. 开始 TDD 执行
```

## 每轮执行流程

```
1. 按启动协议恢复状态，确定当前任务
2. progress.json 中标记该任务 "in_progress"
3. TDD：写全部测试（≥8）→ 确认 RED（全失败）→ 实现 → 确认 GREEN（全过）
4. 验证功能（curl / WebSocket 测试）
5. git add + git commit -m "task-N: <描述>"
6. progress.json 中标记该任务 "done"
```

## 约束

- **单线程串行开发**：禁止并行 agent 写代码
- **禁止假实现**：stub / echo / placeholder 不算 done
- **真实功能验证**：server 类 task 必须启动 + curl 验证
- 只 import 已存在的模块
