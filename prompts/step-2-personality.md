# Step 2：人格系统与防御机制 ✅

## 目标

人格核心 + 防御机制 + 关系演进。

## 已实现

### personality/defense.py — 防御机制（DefenseMechanism）
- 雷区检测：身份质疑 / 日记隐私 / 梦境隐私（正则规则）
- 触发后生成防御指引（转移话题/含糊/温柔拒绝/直接拒绝）
- 根据用户施压程度升级策略（连续逼问 → 升级为强硬拒绝）
- `build_defense_prompt()` 注入 system prompt，由 LLM 自然演绎而非硬编码回复

### personality/relationship.py — 关系演进（RelationshipManager）
- 阶段：初识 → 朋友 → 信赖
- `score_message()` 按情感词打分，`update()` 累积亲密度积分自动晋级
- `build_relationship_prompt()` 注入关系状态，影响回复风格和自我暴露意愿

### agent/loop.py 集成
- `_build_context` 注入人格(SOUL) + 关系状态 + 防御提示
- `_process_message` 调用 relationship.update 更新关系

## 实测验收

- 问"你是不是机器人？" → 触发防御："怎么突然问这个呀…不想聊这个啦"
- 持续友好对话 → 关系阶段从初识演进
- 防御不影响正常对话，且能把话题自然拉回
