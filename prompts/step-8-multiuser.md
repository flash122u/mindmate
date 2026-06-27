# Step 8：多用户支持 ⬜

## 目标

从"单用户写死 default"升级为多用户：每个患者有独立的记忆、关系、情绪锚点、
日记/梦、能量状态。小暖对每个人是"不同的关系、不同的记忆"。

## 现状盘点

| 层 | 多用户就绪度 |
|---|---|
| 存储层（store.py） | ✅ 各表已按 `session_key` 分隔（history/anchors/relationship/diary/dreams/alerts） |
| 后台 API | ✅ 已接受 `session_key` 参数 |
| AgentLoop | ❌ `TurnContext.session_key` 写死 "default" |
| 能量模型 | ❌ 全进程一个共享实例 |
| WebSocket 投递 | ❌ 广播给所有客户端（不分用户） |
| 主动循环 | ❌ 只对 default 一个用户 |
| 用户识别 | ❌ 不存在 |

**关键洞察**：DB 层已经现成，工作量集中在「用户识别 + 运行时状态 per-user 隔离 + 投递路由」。

## 设计

### 8.1 用户识别

- 约定 `session_key = chat_id`，每个 WebSocket 连接携带一个 user_id
- 来源：URL query（`/ws?uid=xxx`）或首条消息里带 uid；无则生成匿名 id
- `InboundMessage.chat_id` 即用户标识；贯穿到 session_key

### 8.2 AgentLoop 用真实 session_key

- `_build_context` / `_process_message` 不再写死 "default"，
  改用 `msg.chat_id`（或新增 `msg.session_key`）
- relationship/anchors/diary 的读写本来就传 session_key → 自动隔离

### 8.3 能量模型 per-user

- 把单个 `EnergyModel` 换成 `EnergyRegistry`：
  ```python
  class EnergyRegistry:
      def get(self, session_key) -> EnergyModel  # 懒创建
  ```
- `on_user_message(session_key)` / `should_reach_out(session_key)` 按用户隔离
- AgentLoop 收到消息 → `registry.get(sk).on_user_message()`

### 8.4 WebSocket 路由（web/app.py）

- 客户端注册时记录 `client → user_id` 映射：`clients: dict[user_id, set[WebSocket]]`
- `OutboundMessage.chat_id` = 目标 user_id
- outbound 消费者只推给该 user 的连接，不再广播
- typing 信号同样按 user 路由

### 8.5 主动循环 per-user

- ProactiveLoop 遍历活跃用户：
  ```python
  for sk in memory.list_sessions():
      ok, _ = registry.get(sk).should_reach_out()
      if ok:
          await agent.generate_proactive(sk)
          registry.get(sk).mark_proactive()
  ```

### 8.6 前端（index.html）

- 进入时生成/读取 localStorage 的 uid，连接 `/ws?uid=xxx`
- 后台 dashboard 加用户切换下拉（`/api/dashboard/users` 列出 session_keys）

## 数据/接口变更

- `store.list_sessions()` 复用 Step 7 的方法
- 新增 `/api/dashboard/users` 返回用户列表
- `InboundMessage`/`OutboundMessage` 用 chat_id 作 user 路由键（已有字段，无需改结构）

## 测试

- 两个不同 session_key 的关系/锚点/记忆互不污染
- EnergyRegistry 为不同用户维护独立状态
- WebSocket 路由：用户 A 的回复不会发给用户 B
- 主动循环对多个用户分别判断
- 后台按 session_key 查询隔离正确

## 验收标准

- 两个浏览器（不同 uid）同时聊天，记忆/关系完全独立
- 小暖对用户 A 已是"信赖"，对用户 B 仍是"初识"
- 用户 A 的主动消息只发给 A
- 后台能切换查看不同用户的数据

## 实施顺序建议

先做 8.1–8.3（识别 + AgentLoop + 能量隔离）打通单连接多用户，
再做 8.4–8.5（投递路由 + 主动循环），最后 8.6 前端。
Step 7（调度器）与本步独立，可先做 Step 7 再做 Step 8，
但 Step 8 完成后调度器的 `active_sessions` 才真正多用户有意义。
