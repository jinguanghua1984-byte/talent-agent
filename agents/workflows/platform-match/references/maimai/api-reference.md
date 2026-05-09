# 脉脉搜索 API 参考

## 搜索 API

- **URL**: `https://maimai.cn/api/pc/search/contacts`
- **Method**: POST
- **Content-Type**: application/json
- **认证**: cookies（需先登录）

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | 是 | 搜索关键词 |
| page | int | 否 | 页码，默认 1 |
| pagesize | int | 否 | 每页条数，默认 30 |

### 响应结构

```json
{
  "code": 0,
  "data": {
    "contacts": [...],
    "total": 100,
    "has_more": true
  }
}
```

### contacts[] 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 脉脉 uid |
| name | string | 姓名 |
| gender_str | int | 性别（1=男, 2=女） |
| age | int | 年龄 |
| city | string | 城市 |
| company | string | 当前公司 |
| position | string | 当前职位 |
| sdegree | int | 最高学历（1=本科, 2=硕士, 3=博士, 4=大专） |
| worktime | string | 工作年限（如 "4年7个月"） |
| hunting_status | int | 求职状态（5=看机会, 0/1-4=不看） |
| active_state | string | 活跃状态 |
| exp[] | array | 工作经历 |
| edu[] | array | 教育经历 |
| exp_tags[] | array | 经验标签 |
| tag_list[] | array | 技能标签 |
| job_preferences | object | 求职意向 |
| detail_url | string | 个人主页 URL |
| user_project[] | array | 项目经历 |

> 注：以上字段基于现有数据推测，需在登录后实测确认完整枚举值。实施时需校准。

## 反爬信号

| 信号 | 处理 |
|------|------|
| 返回验证码页面 | 触发熔断 |
| HTTP 403 | 触发熔断 |
| 连续 3 次空结果 | 触发熔断 |
| 响应 > 10s | 触发熔断 |
