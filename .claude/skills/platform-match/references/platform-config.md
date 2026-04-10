# 平台配置文档

## 脉脉 (maimai)

### 当前支持功能
- **搜索字段**: 姓名、公司、职位
- **组合搜索**: 支持多字段组合（姓名+公司、姓名+职位、公司+职位）
- **数据丰富程度**:
  - 基本信息：姓名、职位、公司、头像
  - 联系方式：邮箱、手机（需权限）
  - 职业历史：工作经历、教育背景
  - 社交信息：关注者、脉币数
  - 动态更新：最近活跃时间、发布内容

### 匹配规则示例

```yaml
# 精确匹配规则
exact:
  姓名+公司:
    pattern: "{{name}} {{company}}"
    fields: ["姓名", "公司"]

  姓名+职位:
    pattern: "{{name}} {{position}}"
    fields: ["姓名", "职位"]

# 模糊匹配规则
fuzzy:
  职位关键词:
    pattern: "{{position}}"
    fields: ["职位"]
    threshold: 0.8
```

### 搜索结果格式
```json
{
  "candidates": [
    {
      "platform": "maimai",
      "profile_url": "https://maimai.cn/profile/xxx",
      "name": "张三",
      "title": "产品经理",
      "company": "阿里巴巴",
      "department": "电商事业部",
      "location": "杭州",
      "industry": "互联网",
      "summary": "10年互联网产品经验...",
      "avatar": "https://avatar.url",
      "verified": true,
      "follow_count": 1234,
      "last_active": "2024-01-15",
      "matched_score": 0.95
    }
  ]
}
```

### 反爬注意事项

1. **请求限制**
   - 单IP每分钟最多10次搜索
   - 建议间隔：至少3秒 between requests
   - 并发限制：单账号最多3个并发连接

2. **特征检测**
   - User-Agent轮换（至少5种不同UA）
   - Cookie管理（每5-10分钟更新一次）
   - 代理IP轮换（推荐动态代理池）

3. **IP管理策略**
   - 使用代理IP池，每个IP执行50-100次后切换
   - 检测IP封锁状态，自动切换可用节点
   - 代理失败重试：最多3次，间隔30秒

4. **账号安全**
   - 使用不同账号轮询（5-10个账号）
   - 模拟真实用户行为（阅读、点赞、评论）
   - 定期更新cookie和token

5. **异常处理**
   - 验码检测：暂停15分钟，更换IP
   - 封号检测：立即切换到备用账号
   - 频率限制： exponential backoff 1-5分钟

---

## BOSS直聘 (boss)

### 后续扩展计划
- **开发阶段**: Phase 2 (预计2024Q2)
- **支持字段**: 姓名、公司、职位、学历
- **特色功能**:
  - BOSS直聊API集成
  - 简历快照抓取
  - 在线状态检测
- **反爬策略**:
  - 模拟移动端H5请求
  - 用户行为模拟
  - 设备指纹管理

---

## 猎聘 (liepin)

### 后续扩展计划
- **开发阶段**: Phase 2 (预计2024Q3)
- **支持字段**: 姓名、公司、职位、薪资范围
- **特色功能**:
  - 简历完整版抓取
  - 求职意向分析
  - 技能标签提取
- **反爬策略**:
  - PC端模拟
  - 简历页详情抓取
  - 动态页面解析

---

## 添加新平台的指引

### 1. 需求分析
- 确定平台的数据源（API/网页）
- 识别关键数据字段
- 评估反爬难度

### 2. 技术调研
- 分析请求结构（GET/POST）
- 确定认证方式（cookie/token）
- 研究搜索API参数

### 3. 模块开发
- 创建新平台的 scraper 模块
- 实现搜索逻辑
- 添加结果解析器

### 4. 集成到系统
- 更新 `platform-config.md` 文档
- 修改 `SKILL.md` 添加平台支持
- 更新 `data-manager.py` 的新平台命令

### 5. 测试验证
- 执行功能测试（10+个搜索案例）
- 压力测试（100+请求）
- 稳定性测试（24小时运行）

### 6. 文档更新
- 添加平台配置
- 更新使用指南
- 记录注意事项

### 平台接入清单
```yaml
platform_requirements:
  name: 平台名称
  api_endpoint: "API地址"
  auth_method: "认证方式"
  search_fields: ["支持字段列表"]
  rate_limit: "请求频率限制"
  anti_scraping_level: 1-3 # 1简单, 2中等, 3困难
  estimated_development_days: 10
```

### 文件结构约定
```
.claude/skills/platform-match/
├── platforms/
│   ├── [platform-name]/
│   │   ├── scraper.py          # 搜索抓取器
│   │   ├── parser.py           # 结果解析器
│   │   ├── config.yaml         # 平台配置
│   │   └── tests/              # 测试用例
└── references/
    └── platform-config.md      # 本文件
```