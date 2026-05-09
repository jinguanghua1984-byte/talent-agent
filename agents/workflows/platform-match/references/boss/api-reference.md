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
1. 在 search_frame 中找到 `.search-input` 输入框（**不是** `.input-text`，那是另一个筛选条件的输入框）
2. 先清空职位筛选：`.search-current-job` → 点击 → 选"不限职位"（否则搜索结果可能为空）
3. `click()` → `Control+a` → `Backspace`（**不能用 fill("")**，Vue 组件不响应）
4. `type(query, delay=100)` → `Enter` 或点击 `.icon-search`
5. 在 **page 级别**（不是 frame 级别）注册 `page.on('response')` 拦截 `geeks.json`
6. 翻页：滚动 search_frame 和 page 到底部触发无限滚动，拦截新 page 的响应

**注意**: `on_response` 回调是同步的，`response.json()` 是异步方法。
在回调内不能 await，需保存 response 对象到外部变量，在回调外再 await。

**API 实际 URL 格式**:
```
/wapi/zpitem/web/boss/search/geeks.json?page=1&jobId={encryptJobId}&keywords={query}&tag=&city={cityCode}&gender=-1&experience=-1,-1&...
```

注意: `jobId` 是当前选中的职位 ID。搜索栏有职位筛选下拉（`.search-current-job`），
默认绑定到某个具体职位，会导致搜索结果仅匹配该职位要求。每次搜索前需清空为"不限职位"。

**分页**: Boss 使用无限滚动加载（无分页按钮），滚动到底部自动触发下一页请求。
响应中 `hasMore: false` 表示已到最后一页。

## 反爬检测

**已确认**:
- `page.evaluate(fetch)` 触发反爬 → 强制登出（code: 7）
- `context.new_page()` + `page.goto()` 触发 `browser-check.min.js` → 强制登出
- **必须复用已有页面** `context.pages[0]`，不能创建新 tab

**解决方案**: 复用已有登录页面，在 iframe 中模拟用户输入搜索。

## 详情 API

**不可用**（2026-04-24 确认）。

### 不可行的方案

| 方案 | 结果 |
|------|------|
| `page.goto('/web/geek/{id}')` | 触发 browser-check.min.js → 强制登出（404 页面） |
| `page.evaluate(fetch)` | 触发反爬检测 code: 7 → 强制登出 |
| `context.new_page()` | 触发 browser-check.min.js → 强制登出 |

### 侧边面板（.geek-detail）

点击搜索结果卡片后在主页面右侧弹出，仅包含摘要信息：
- 姓名、年龄、工作经验、学历、求职状态、期望薪资
- 活跃状态
- 技能标签
- 期望职位
- 当前公司·职位（仅最近一段）
- 院校·专业（仅一段）

不包含完整工作经历列表、项目经历、自我评价。

### 可用数据来源

搜索 API 的 `geekCard` 已包含大部分可用字段：
- 基本信息：name, city, gender, ageDesc, workYear, highestDegreeName, salary, activeDesc
- 当前职位：geekWork.name（公司·职位）
- 期望职位：expect.name
- 技能标签：labelMatchList[].markWord
- 工作经历列表：workList[]（每项含 name + dateRange）
- 教育经历：geekEdu.name（国家·学校·专业）
- 唯一标识：encryptGeekId, securityId

可满足 `enrichment_level: "partial"` 的入库需求。
