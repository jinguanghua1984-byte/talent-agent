# Boss 直聘搜索 API 参考

> 状态: 待调研（阶段 1）

## 搜索 API

- **端点**: 待确认
- **方法**: 待确认（预估 GET）
- **Content-Type**: 待确认

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | 是 | 搜索关键词 |
| page | int | 否 | 页码 |
| pageSize | int | 否 | 每页数量 |
| city | string | 否 | 城市筛选 |
| education | string | 否 | 学历筛选 |
| workYear | string | 否 | 工作年限筛选 |

### 响应结构

待调研填写。

## 详情 API

待调研填写。

## 验收标准

- [ ] 确认搜索 API 端点 URL
- [ ] 确认请求方式（GET/POST）
- [ ] 确认请求参数结构
- [ ] 确认响应结构
- [ ] 确认是否有签名/加密机制
- [ ] 确认 encryptUserName 跨 session 稳定性
- [ ] 能用 page.evaluate(fetch) 成功获取 JSON 响应
