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
- `geekWork.name` 格式: 公司名和职位名混合文本（如"字节跳动大模型算法"），列表页无法分离公司和职位
- `current.name` 格式: 期望职位（如"期望职位 大模型算法"）
- `geekEdu.name` 格式: `国家·学校·专业`（·分隔）
- `workList[].name` 格式: 公司名和职位名混合文本（无分隔符），列表页无法分离
- `workList[].dateRange` 格式: `YYYY-YYYY`
- `labelMatchList[].markWord` 为标签文本（技能/学校标签等）

## 搜索触发方式

搜索页在 iframe 中加载（`/web/frame/search/`），不会通过 URL 导航触发 API。

**正确的触发流程**:
1. 在 `page.frames[1]` 中找到 `.input-text` 输入框
2. `click()` → `Control+a` → `type(query, delay=50)`
3. 点击 `.icon-search` 搜索图标
4. 在 **page 级别**（不是 frame 级别）注册 `page.on('response')` 拦截 `geeks.json`

**API 实际 URL 格式**:
```
/wapi/zpitem/web/boss/search/geeks.json?page=1&jobId={encryptJobId}&keywords={query}&tag=&city={cityCode}&gender=-1&experience=-1,-1&...
```

注意: `jobId` 是当前选中的职位 ID，搜索结果会基于该职位进行匹配。

## 反爬检测

**已确认**:
- `page.evaluate(fetch)` 触发反爬 → 强制登出（code: 7）
- `context.new_page()` + `page.goto()` 触发 `browser-check.min.js` → 强制登出
- **必须复用已有页面** `context.pages[0]`，不能创建新 tab

**解决方案**: 复用已有登录页面，在 iframe 中模拟用户输入搜索。

## 详情 API

待调研（需 securityId 访问候选人详情页）。
