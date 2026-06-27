# Step 7：定时任务 — 每日日记/梦自动生成 ⬜

## 目标

让小暖的「私密内在生活」真正自动运转：每天自动写一篇日记、做一个梦，
无需手动调用 `run_daily_inner_life`。这样她才像"每天都在生活着"。

## 现状

- `AgentLoop.run_daily_inner_life(session_key)` 已实现（写日记 + 造梦）
- 但没有调度器触发它，目前要手动调用
- 日记/梦存入私密表，分享冲动机制已就绪（Step 6）

## 设计

### 7.1 调度器（agent/scheduler.py 新建）

采用**轻量 asyncio 循环**（不引入 APScheduler，保持零额外依赖，与项目风格一致）：

```python
class DailyScheduler:
    """每天在指定时段触发一次每日任务。"""
    def __init__(self, run_cb, hour=3, check_interval_s=600):
        # run_cb: async (session_key) -> None
        # hour: 每天几点跑（默认凌晨3点，安静时段）
        # _last_run_date: dict[session_key, "YYYY-MM-DD"] 防重复
    async def run(self):
        while running:
            await sleep(check_interval_s)
            now = datetime.now()
            if now.hour == self.hour:
                for sk in active_sessions():
                    if last_run[sk] != today:
                        await run_cb(sk)
                        last_run[sk] = today
```

要点：
- 凌晨跑（符合"夜里做梦、睡前写日记"的设定）
- `_last_run_date` 防同一天重复触发
- 通过回调拿到「活跃用户列表」，对每个用户各跑一次

### 7.2 活跃用户来源（store.py 加方法）

```python
def list_sessions(self) -> list[str]:
    """返回所有有过对话的 session_key（去重）。"""
    # SELECT DISTINCT session_key FROM history
```

### 7.3 接线（main.py）

```python
scheduler = DailyScheduler(
    run_cb=agent.run_daily_inner_life,
    active_sessions=agent.memory.list_sessions,
    hour=3,
)
asyncio.create_task(scheduler.run())
```

### 7.4 可配置项（config/settings.py）

- `INNER_LIFE_HOUR`（默认 3）
- `INNER_LIFE_ENABLED`（默认 true）

## 测试

- 调度器在非目标时段不触发
- 到达目标时段触发，且同一天只触发一次
- `list_sessions` 正确去重返回活跃用户
- 触发后日记/梦确实写入对应 session 的私密表
- 用可注入的 `now` / 时钟使测试确定性（参考 energy.py 的 now 参数模式）

## 验收标准

- 服务跑过一夜后，每个活跃用户的私密表里多了当天的日记 + 梦
- 同一天不会重复生成
- 日记/梦仍然私密，只在交心时刻吐露（不主动推送）
