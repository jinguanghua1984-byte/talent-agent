---
name: platform-match
description: 招聘平台匹配——在脉脉等招聘平台上搜索候选人，丰富候选人信息
---

# platform-match Skill

## 功能描述

在招聘平台上搜索和匹配候选人，自动丰富候选人池信息。目前支持脉脉平台，后续将扩展更多平台。

## 触发方式

```
/platform-match [--platform maimai] [--rules "姓名+公司"] [--candidates <filter>]
```

### 参数说明
- `--platform`: 指定搜索平台，默认 `maimai`
- `--rules`: 匹配规则，默认 `"姓名+公司"`
- `--candidates`: 候选人过滤条件（可选）

## 工作流程

### 阶段 1: 读取候选人列表
调用 `data-manager.py candidate list` 获取待搜索的候选人列表。

### 阶段 2: 生成匹配计划
- 根据搜索规则生成搜索关键词
- 展示搜索计划摘要
- 输出详细计划到 `data/output/platform-match-plan.md`
- 等待用户确认

### 阶段 3: 执行平台搜索
逐个执行平台搜索：
- 脉脉使用 `skills/platform-match/modules/maimai-scraper`
- 支持并发搜索（最多5个）
- 每个搜索间隔3秒避免触发反爬

### 阶段 4: 丰富候选人信息
- 解析搜索结果
- 更新候选人详细信息
- 输出结果报告到 `data/output/platform-match-results.md`
- 等待用户确认

### 阶段 5: 更新候选人池
- 更新已匹配候选人的 `enrichment_level`
- 向 `sources` 字段追加平台信息
- 保留未匹配的候选人（不删除）
- 提交数据变更

## 使用示例

### 示例 1: 基础搜索
```
/platform-match
```
- 默认搜索规则：姓名+公司
- 默认平台：脉脉
- 搜索所有待匹配候选人

### 示例 2: 指定平台和规则
```
/platform-match --platform maimai --rules "姓名+职位"
```
- 使用姓名+职位组合搜索
- 仅在脉脉平台搜索

### 示例 3: 筛选特定候选人
```
/platform-match --candidates "status=pending"
```
- 只搜索状态为 pending 的候选人

## 数据格式

### 候选人列表（输入）
```json
{
  "candidates": [
    {
      "id": "001",
      "name": "张三",
      "company": "阿里巴巴",
      "position": "产品经理",
      "enrichment_level": "basic",
      "sources": []
    }
  ]
}
```

### 搜索计划（输出）
```markdown
# 平台匹配计划

## 平台: 脉脉
## 搜索规则: 姓名+公司

### 待搜索候选人 (3人)
1. 张三 - 阿里巴巴
2. 李四 - 腾讯
3. 王五 - 百度

## 预计耗时: 5分钟
## 确认开始搜索吗？(y/n)
```

### 搜索结果（输出）
```markdown
# 平台匹配结果

## 成功匹配 (2/3)

### 张三 - 阿里巴巴
- 匹配得分: 95%
- 更新信息:
  - 部门: 电商事业部
  - 位置: 杭州
  - 行业: 互联网
  - 最后活跃: 2024-01-15
  - 关注者: 1234
- 状态: 已更新

### 李四 - 腾讯
- 匹配得分: 88%
- 更新信息:
  - 部门: 社交网络事业群
  - 位置: 深圳
  - 行业: 互联网
  - 最后活跃: 2024-01-10
  - 关注者: 856
- 状态: 已更新

## 未匹配 (1/3)
### 王五 - 百度
- 原因: 未在脉脉找到匹配结果
- 状态: 保留，下次重试
```

## 技术实现

### 核心模块
- `skills/platform-match/modules/maimai-scraper/`
  - `form-filler.py`: 搜索表单填写
  - `loop-orchestrator.py`: 循环执行控制
  - `result-merger.py`: 结果合并处理

### 输出目录
- `data/output/platform-match-plan.md`: 匹配计划
- `data/output/platform-match-results.md`: 搜索结果

### 数据管理
- 使用 `data-manager.py` 候选人管理命令
- 自动提交数据变更到 Git
- 支持增量更新，不覆盖已有数据

## 注意事项

1. **匹配原则**
   - 匹配不基于JD，只是丰富信息
   - 匹配失败的候选人保留，不删除
   - 支持多次匹配，逐步丰富信息

2. **性能考虑**
   - 单次搜索批量处理最多20个候选人
   - 超过20个自动分批处理
   - 每批间隔5分钟

3. **反爬保护**
   - 默认搜索间隔3秒
   - 支持代理IP轮换
   - 自动检测验证码

4. **数据安全**
   - 所有数据本地存储
   - 敏感信息加密处理
   - 支持数据备份和恢复

## 配置说明

详细的平台配置参考：`skills/platform-match/references/platform-config.md`

## 故障排除

### 常见问题
1. **搜索失败**
   - 检查网络连接
   - 验证平台API可用性
   - 查看日志文件 `logs/platform-match.log`

2. **匹配不准确**
   - 调整搜索规则
   - 检查输入数据格式
   - 参考平台配置优化搜索策略

3. **性能问题**
   - 减少并发数量
   - 延长搜索间隔
   - 使用代理IP池

### 日志查看
```bash
# 查看实时日志
tail -f logs/platform-match.log

# 搜索错误日志
grep "ERROR" logs/platform-match.log
```