# Boss 直聘搜索 API 参考

> 状态: 已校准（2026-04-20）

## 搜索 API

- **端点**: `https://www.zhipin.com/wapi/zpitem/web/boss/search/geeks.json`
- **方法**: GET
- **Content-Type**: application/json（响应）

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keywords | string | 是 | 搜索关键词 |
| page | int | 否 | 页码（从 1 开始） |
| pageSize | int | 否 | 每页数量（默认 30） |
| city | string | 否 | 城市筛选 |
| degree | string | 否 | 学历筛选 |
| workYear | string | 否 | 工作年限筛选 |

### 响应结构

```json
{
  "code": 0,
  "message": "Success",
  "zpData": {
    "hasMore": true,
    "totalCount": 400,
    "segs": "产品经理",
    "geeks": [
      {
        "geekCard": {
          "name": "王**",
          "gender": 1,
          "city": "大连",
          "workYear": "4年",
          "salary": "15-25K",
          "ageDesc": "27岁",
          "activeDesc": "刚刚活跃",
          "highestDegreeName": "硕士",
          "encryptGeekId": "...",
          "securityId": "...",
          "geekWork": {"name": "百度·PSIG·产品经理"},
          "geekEdu": {"name": "英国·曼彻斯特大学·人力资源管理与产业关系"},
          "labelMatchList": [{"markWord": "QS前100院校", "type": 2}],
          "workList": [
            {"name": "百度·PSIG·产品经理", "dateRange": "2024-2026"}
          ],
          "lidTag": "用户研究",
          "eduSchool": "英国·曼彻斯特大学",
          "eduMajor": "人力资源管理与产业关系"
        }
      }
    ]
  }
}
```

### 关键说明

- 候选人数据在 `zpData.geeks[].geekCard` 下
- `gender`: 0=未知, 1=男, 2=女
- `geekWork.name` 格式: `公司·部门·职位`（·分隔，取第一段为公司，最后一段为职位）
- `geekEdu.name` 格式: `国家·学校·专业`
- `workList[].name` 格式: `公司·职位`
- `workList[].dateRange` 格式: `YYYY-YYYY`
- `labelMatchList[].markWord` 为标签文本（技能/学校标签等）

## 反爬检测

**已确认**: `page.evaluate(fetch)` 会触发反爬，导致强制登出（code: 7）。
**解决方案**: 使用被动网络拦截（`ctx.on('response')`）在用户手动搜索时捕获响应。

## 详情 API

待调研（需 securityId 访问候选人详情页）。
