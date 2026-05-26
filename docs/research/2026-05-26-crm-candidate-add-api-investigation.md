# CRM 新增人才 API 调查记录

日期：2026-05-26

目标系统：`http://101.200.132.164/crm`

目标动作：新增人才

边界：

- 只在用户授权登录态下观察和复现用户已有权限的操作。
- 不绕过登录、验证码、风控或权限校验。
- 不记录 Cookie、token、密码、验证码或真实候选人隐私。
- 所有直接 API 复现应先使用测试数据，正式写入前需要人工确认。

## 当前结论

新增人才入口为：

```text
/crm#candidate/add
```

保存接口由前端通用 meta 表单框架生成：

```text
POST /rest/candidate/add
```

请求体形态：

```http
Content-Type: application/x-www-form-urlencoded; charset=UTF-8

data=<JSON string>
```

证据来自登录后加载的 `framework.min.js`：

```js
SAVE_URL: "/rest/{0}/add"
```

`candidate` 模型代入后得到 `/rest/candidate/add`。保存逻辑为：

```js
hub.publish("ajax", {
  url: b._saveUrl,
  data: { data: JSON.stringify(d) },
  type: "post"
})
```

保存前会把表单数据组装为 `d`，并补充：

```js
d.record_type = b.suffix
```

## 表单字段映射

登录后打开 `#candidate/add`，当前页面可见字段如下。字段名来自 DOM 的 `name` 属性，中文含义来自页面可见标签。

### 顶层字段

| 字段 | 页面含义 | 备注 |
| --- | --- | --- |
| `type` | 候选人 / Cold Call / 联系人 | 当前默认 `candidate` |
| `attachments` | 附件 | 文本字段，文件上传另走上传逻辑 |
| `attachment-type` | 附件类型 | 默认 `Original CV` |
| `avatar` | 照片 | 文件/文本字段 |
| `email` | 私人邮箱 |  |
| `email1` | 工作邮箱 |  |
| `email2` | 其他邮箱 |  |
| `mobile` | 手机 |  |
| `mobile1` | 工作电话 |  |
| `mobile2` | 其他电话 |  |
| `englishName` | 英文名 |  |
| `chineseName` | 中文名 |  |
| `gllueext113` | 花名 | 自定义字段 |
| `gllueextWechat` | 微信号 | 自定义字段 |
| `gender` | 性别 | `true`=男，`false`=女 |
| `_ext4` | 出生年月 | cold call 模式下非必填 |
| `locations` | 所在城市 | 选择器字段 |
| `citys` | 意向城市 | 选择器字段 |
| `industrys` | 行业 | 选择器字段 |
| `functions` | 职能 | 选择器字段 |
| `gllueextfirstdegree` | 第一学历 | 选项编码字段 |
| `annualSalary` | 年薪 | 单位：万 |
| `channel` | 渠道 | 选择器字段 |
| `owner` | 拥有者 | 当前值 `300`，页面显示 Daicy |
| `_ext1` | 婚育 | 选项字段 |
| `folders` | 文件夹 | 选择器字段 |
| `source` | 录入方式 | 禁用字段，当前值 `gllue`，页面显示手工录入 |
| `gllueext112` | 星座 | 自定义字段 |
| `gllueext114` | 泰伦职级 | 自定义字段 |
| `gllueextNBC` | 是否加入 Talent Pool | 选项编码字段 |

### Cold Call 必填项补证

用户结合页面表单确认：`coldcall` 模式下必填项为电话三选一、姓名、性别、所在城市、行业、职能、渠道、工作经历公司和职位。除这些字段外，其余字段都可以不填；`owner`、`source` 等字段可能由前端默认值或 payload 模式补充，但不作为表单必填项。

### 工作经历字段

DOM 字段使用 `____40` 后缀标识同一个工作经历面板。前端 `meta-rfk-add-widget` 会把这类 panel 组装为数组字段。预期 JSON 字段为 `candidateexperience_set`。

| 字段 | 页面含义 |
| --- | --- |
| `started-year____40` | 开始年 |
| `started-month____40` | 开始月 |
| `ended-year____40` | 结束年 |
| `ended-month____40` | 结束月 |
| `current____40` | 目前在职 |
| `company_name____40` | 公司 |
| `title____40` | 职位 |
| `company_city____40` | 公司城市 |
| `company_industry____40` | 公司行业 |
| `description____40` | 描述 |
| `department____40` | 部门 |
| `gllueextTitle____40` | 公司职级 |

前端历史样本中可见的服务端结构示例：

```json
{
  "candidateexperience_set": [
    {
      "start": "1111-02",
      "end": null,
      "is_current": true,
      "client": {"id": 60, "name": "example"},
      "title": "example",
      "description": null,
      "lang": "default"
    }
  ]
}
```

### 教育经历字段

DOM 字段使用 `____41` 后缀标识同一个教育经历面板。预期 JSON 字段为 `candidateeducation_set`。

| 字段 | 页面含义 |
| --- | --- |
| `started-year____41` | 开始年 |
| `started-month____41` | 开始月 |
| `ended-year____41` | 结束年 |
| `ended-month____41` | 结束月 |
| `current____41` | 在读 |
| `school____41` | 学校 |
| `degree____41` | 学历 |
| `major____41` | 专业 |

## 待确认

内置 Browser 当前未暴露 network/HAR 和 Cookie 导出接口，因此还需要一次真实保存请求来确认：

- 完整请求头中除 Cookie 以外是否有 CSRF、X-Requested-With、租户或签名字段。
- `data` JSON 的精确嵌套结构，尤其 `locations`、`citys`、`industrys`、`functions`、`channel` 这类选择器字段是纯 ID、对象还是数组对象。
- 成功响应格式，预计包含 `status` 和 `data`，其中 `data` 可能为新建 candidate id 或对象。
- 失败响应格式和重复候选人校验方式。

## 下一步抓包动作

推荐使用 DevTools 手动补证：

1. 在 CRM 页面按 `F12` 或 `Ctrl+Shift+I` 打开 DevTools。
2. 进入 `Network`，勾选 `Preserve log`。
3. 过滤 `Fetch/XHR`。
4. 清空 Network。
5. 使用测试数据手动填写新增人才表单。
6. 点击保存。
7. 找到 `POST /rest/candidate/add`。
8. 右键请求，选择 `Copy` -> `Copy as cURL`。
9. 将 cURL 内容保存到本地临时文件，先删除或替换 Cookie/token 后再交给我分析。

脱敏建议：

```text
Cookie: [REDACTED]
X-CSRFToken: [REDACTED]
Authorization: [REDACTED]
```

拿到 cURL 后，下一步生成：

- `docs/research/2026-05-26-crm-candidate-add-api-contract.md`
- 最小 Python client 草案
- CLI 命令设计，例如 `crm-cli candidate add --input candidate.json --dry-run`
