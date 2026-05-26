# CRM 新增人才 API 合同草案

日期：2026-05-26

状态：已确认请求形态、成功响应格式、字段元数据接口以及主要树形/外键查询接口，待补证错误响应和真实写入前的重复校验。

## 安全边界

- 本文不保存 Cookie、token、密码、验证码或真实候选人隐私。
- 原始 cURL 中的 Cookie 只能用于本次人工验证，不得提交到仓库。
- 后续 CLI 必须从环境变量或本机安全配置读取登录态，不能把登录态写进代码、配置样例或日志。

## Endpoint

```http
POST http://101.200.132.164/rest/candidate/add?_v=<cache-or-request-version>&_v_user=<user-id>
```

当前观测：

```text
_v=n6020212249708101
_v_user=300
```

判断：

- `_v_user` 是当前用户 id。
- `_v` 看起来是前端生成的版本/请求参数，不应硬编码；后续客户端可先不传，若服务端要求再按当前页面请求方式补。

## Headers

必要或建议保留：

```http
Accept: */*
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
Origin: http://101.200.132.164
Referer: http://101.200.132.164/crm
X-Requested-With: XMLHttpRequest
x-request-id: <milliseconds timestamp>
Cookie: <runtime session cookies>
```

当前 cURL 未观察到：

```text
Authorization
X-CSRFToken
X-CSRF-Token
```

## Body

请求体是 `application/x-www-form-urlencoded`，只有一个关键参数：

```text
data=<urlencoded JSON string>
```

其中 `data` 解码后是新增人才 JSON。

## Payload Schema

### 顶层字段

```json
{
  "attachments": "",
  "avatar_id": null,
  "email": "string",
  "email1": "string",
  "email2": "string",
  "mobile": "string",
  "mobile1": "string",
  "mobile2": "string",
  "englishName": "string",
  "chineseName": "string",
  "gllueext113": "string",
  "gllueextWechat": "string",
  "gender": true,
  "_ext4": "YYYY-MM-DD",
  "locations": "102,212",
  "citys": "102,125,212,306,508",
  "industrys": "4,75,200",
  "functions": "1267,1286,1288,1290,1418",
  "gllueextfirstdegree": "n75722502808443490",
  "annualSalary": 5000000,
  "channel": "400034",
  "owner": "300",
  "shares": [],
  "_ext1": "已婚",
  "folders": ["13009"],
  "source": "gllue",
  "type": "coldcall",
  "gllueext112": "n81682323688982850",
  "gllueext114": "n73407498137465810",
  "gllueextNBC": "n51095470956125190",
  "candidateexperience_set": [],
  "candidateproject_set": [],
  "candidateeducation_set": [],
  "note_set": {},
  "record_type": "coldcall"
}
```

### 类型说明

脱敏 payload 样例模板见 `docs/research/candidate-add-api-post-data.json`。该文件只保留字段结构，不保存原始请求中的邮箱、手机号、真实姓名或内部候选人 ID。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `gender` | boolean | `true`=男，`false`=女 |
| `annualSalary` | number | 页面显示单位为万，但实际 payload 为数字；需业务侧确认单位含义 |
| `locations` | string | 逗号分隔的地区 ID |
| `citys` | string | 逗号分隔的意向城市 ID |
| `industrys` | string | 逗号分隔的行业 ID |
| `functions` | string | 逗号分隔的职能 ID |
| `folders` | string[] | 文件夹 ID 数组 |
| `shares` | array | 共享对象数组，当前为空 |
| `type` | string | `candidate` / `coldcall` / `contact` |
| `record_type` | string | 与 `type` 一致 |

### Cold Call 表单必填规则

用户结合页面表单补证：`coldcall` 模式下，前端表单必填字段只有：

- 电话三选一：`mobile` / `mobile1` / `mobile2`
- 姓名：`englishName` / `chineseName` 至少一个
- `gender`
- `locations`
- `industrys`
- `functions`
- `channel`
- 工作经历至少一条，且每条用于新增的人才工作经历需要公司和职位：`candidateexperience_set[].client` / `candidateexperience_set[].title`

除以上表单字段外，`owner`、`source`、`folders`、`citys`、教育经历、备注、自定义扩展字段等都不作为 cold call 表单必填。`type` / `record_type` 是 payload 模式标记，CLI 仍校验二者非空且一致。

### Cold Call compose 默认规则

当人工草稿缺少以下必填业务字段时，CLI 在 `candidate compose` 阶段使用默认值补齐后再走 lookup：

| payload 字段 | 默认输入值 | lookup 规则 | 当前只读验证结果 |
| --- | --- | --- | --- |
| `gender` | 男 | 转为 boolean `true` | 本地枚举已验证 |
| `industrys` | `AI` | 精确匹配优先；无精确时按 label/path 包含关系取首个 | `AI` -> `188` |
| `functions` | `AI产品` | 精确匹配优先；无精确时按 label/path 包含关系取首个 | `AI产品` -> `1330` |
| `channel` | `脉脉-企业版付费账号` | 先按用户默认名查找；找不到时兼容真实 CRM label `脉脉-企业付费账号` | `脉脉-企业付费账号` -> `400034` |

若默认值和兼容别名都无法在 lookup cache 中命中，CLI 会失败并提示 `请确认 CRM 中的准确选项名称`，由用户补充或修正默认 label。当前真实渠道字典中没有 `脉脉-企业版付费账号`，实际存在的是 `脉脉-企业付费账号`。

## 工作经历

字段：`candidateexperience_set`

```json
[
  {
    "department": "306319",
    "title": "string",
    "description": "string",
    "gllueextTitle": "string",
    "is_current": 1,
    "client": {
      "industrys": "",
      "citys": "",
      "id": 46033,
      "name": "company name"
    },
    "start": "YYYY-MM",
    "end": null,
    "lang": "default"
  }
]
```

规则：

- `is_current=1` 时 `end=null`。
- 非当前经历使用 `is_current=0` 且 `end="YYYY-MM"`。
- `client.id` 是公司 ID，`client.name` 是公司名；自动化前需要先解决公司查询/匹配接口。
- `department` 是部门 ID，可为空字符串。

## 教育经历

字段：`candidateeducation_set`

```json
[
  {
    "school": "school name",
    "degree": "Bachelor",
    "major": "major name",
    "is_current": 0,
    "start": "YYYY-MM",
    "end": "YYYY-MM",
    "lang": "default"
  }
]
```

当前观测到的 degree 值：

```text
Bachelor
Master
```

页面下拉显示为中文学历，但提交值使用英文编码。

## 备注

字段：`note_set`

```json
{
  "status": "Active",
  "content_69": "note content",
  "category": "Candidate Call",
  "date": "YYYY-M-D HH:mm:ss",
  "noteuser_set": [
    {
      "user": 300
    }
  ]
}
```

## 最小请求样例

下面是脱敏后的请求形态。实际 Cookie 只能从本地环境读取。

```bash
curl 'http://101.200.132.164/rest/candidate/add?_v=<request-version>&_v_user=300' \
  -H 'Accept: */*' \
  -H 'Content-Type: application/x-www-form-urlencoded; charset=UTF-8' \
  -H 'Origin: http://101.200.132.164' \
  -H 'Referer: http://101.200.132.164/crm' \
  -H 'X-Requested-With: XMLHttpRequest' \
  -H 'x-request-id: <milliseconds timestamp>' \
  -H 'Cookie: [REDACTED]' \
  --data-urlencode 'data={"mobile":"00000000000","chineseName":"测试候选人","gender":true,"locations":"102","industrys":"4","functions":"1267","channel":"400034","candidateexperience_set":[{"client":{"id":46033,"name":"示例公司"},"title":"示例职位","lang":"default"}],"type":"coldcall","record_type":"coldcall"}'
```

## Python Client 草案

```python
import json
import os
import time

import requests


BASE_URL = os.environ.get("CRM_BASE_URL", "http://101.200.132.164")
CRM_COOKIE = os.environ["CRM_COOKIE"]


def add_candidate(payload: dict) -> dict:
    url = f"{BASE_URL}/rest/candidate/add"
    headers = {
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/crm",
        "X-Requested-With": "XMLHttpRequest",
        "x-request-id": str(int(time.time() * 1000)),
        "Cookie": CRM_COOKIE,
    }
    response = requests.post(url, headers=headers, data={"data": json.dumps(payload, ensure_ascii=False)})
    response.raise_for_status()
    return response.json()
```

## 成功响应

成功响应结构已确认：

```json
{
  "status": true,
  "current_message": {
    "candidateexperience": [
      {
        "status": true,
        "current_message": {},
        "data": "<candidateexperience_id>"
      }
    ],
    "candidateeducation": [
      {
        "status": true,
        "current_message": {},
        "data": "<candidateeducation_id>"
      }
    ]
  },
  "data": "<candidate_id>"
}
```

字段说明：

| 字段 | 含义 |
| --- | --- |
| `status` | 顶层保存是否成功 |
| `data` | 新建人才 candidate id |
| `current_message.candidateexperience[]` | 每条工作经历保存结果 |
| `current_message.candidateexperience[].data` | 新建工作经历 id |
| `current_message.candidateeducation[]` | 每条教育经历保存结果 |
| `current_message.candidateeducation[].data` | 新建教育经历 id |

客户端判断规则：

- 顶层 `status === true` 且 `data` 存在，视为 candidate 创建成功。
- 若工作经历/教育经历数组存在，应逐项检查子项 `status`。
- 任一子项 `status !== true` 时，应把 candidate id 和失败子项一起报告，避免误判为完整成功。

## 错误响应与安全预检

### 登录态失效

已确认无 Cookie 调详情元数据接口时，服务端仍返回 HTTP 200 和 JSON 业务错误：

```http
GET /rest/custom_field/candidate/detail?suffix=coldcall
```

```json
{
  "status": false,
  "message": "login required"
}
```

CLI 已把这种 `status=false` 响应当作失败处理，不会把它缓存成字段元数据：

```text
python scripts/crm_cli.py auth check --no-cookie --suffix coldcall
```

### 重复候选人预检

前端脚本中发现邮箱自动补全接口，可作为真实写入前的只读重复候选人预检：

```http
GET /rest/candidate/email_autocomplete?email=<email>&type=<candidate-type>
```

脚本证据来自 `shared.min.js`：邮箱控件调用 `/rest/candidate/email_autocomplete`，参数为 `email`，并可携带 `type`。

当前 CLI 已封装为：

```text
python scripts/crm_cli.py candidate duplicate-check --email <email> --type coldcall
```

返回码约定：

| 返回码 | 含义 |
| --- | --- |
| `0` | 未发现邮箱匹配项 |
| `2` | 发现可能重复候选人，调用方应阻断新增 |
| `1` | 登录态、请求或响应结构错误 |

CLI 输出会脱敏查询邮箱，只保留命中数量。该预检不等价于保存接口的重复失败响应；它用于在开放真实写入前降低误写风险。

## 详情字段元数据接口

保存成功并跳转详情页后，前端会请求候选人详情页字段配置：

```http
GET http://101.200.132.164/rest/custom_field/candidate/detail?_v=<cache-or-request-version>&_v_user=<user-id>&suffix=coldcall
```

当前观测：

```text
_v=n6020212249708101
_v_user=300
suffix=coldcall
```

请求特点：

- 使用 Cookie 登录态鉴权。
- 请求头形态与新增接口相近，保留 `Referer`、`X-Requested-With: XMLHttpRequest`、`x-request-id` 即可。
- 无请求体。
- `suffix` 与新增 payload 中的 `type` / `record_type` 对应；本次是 `coldcall`。

响应顶层结构：

```json
{
  "html": null,
  "list": []
}
```

`list[]` 同时包含分组和字段。常用字段如下：

| 字段 | 说明 |
| --- | --- |
| `entry_type` | `group` 或 `field` |
| `name` | payload 字段名或分组名 |
| `label_value` / `cn` / `en` | 页面展示名称 |
| `type` | 字段控件类型，例如 `char`、`date`、`integer`、`radio`、`dropdown`、`comtree`、`foreignkey`、`reverse_foreignkey` |
| `group` | 所属页面分组 |
| `data_model_name` / `model_name` | 归属模型，当前为 `candidate` |
| `editable` / `hidden` / `searchable` | 页面行为配置 |
| `order` | 页面排序 |
| `meta_class` | 选项、树形或外键元数据 |
| `option_key` | 选项类型 key |

本次响应未看到明确的 `required` 字段；cold call 表单必填规则已由用户结合页面表单补证，见上文“Cold Call 表单必填规则”。

### 已确认的选项字典

详情字段元数据已经能覆盖一部分本地校验和 label/code 映射：

| payload 字段 | 控件类型 | 取值来源 | 已观测取值 |
| --- | --- | --- | --- |
| `type` | `radio` | `candidate_type` | `candidate`=候选人，`coldcall`=Cold Call，`contact`=联系人 |
| `gender` | `radio` | `candidate_gender` | `true`=男，`false`=女；payload 中观测为 boolean |
| `gllueextfirstdegree` | `radio` | `candidate_gllueextfirstdegree` | `n75722502808443490`=985/211，`n61424932688313930`=双一流，`n19290024848687692`=国内本科，`n1719846207715969`=海外，`n42274261183520180`=大专 |
| `_ext1` | `dropdown` | `candidate__ext1` | 未婚、已婚、已婚已育、离异 |
| `gllueext112` | `dropdown` | `candidate_gllueext112` | 12 星座枚举；本次 payload 中 `n81682323688982850`=摩羯座 |
| `gllueext114` | `dropdown` | `candidate_gllueext114` | R、AC、C、MC、SC、EC、Pre Manager、Manager、BP、MP、SMP、TA、HRBP、BS、BO、BD、FA、Intern |
| `gllueextNBC` | `radio` | `candidate_gllueextNBC` | `n3901397885920277`=YES，`n51095470956125190`=NO |

### 查询接口补证结果

字段元数据接口只告诉控件类型和数据源名称；下面这些端点已用登录态 CDP 抓包/同源 `fetch` 验证。除新增保存接口外，这些查询端点在本次验证中不带 `_v` / `_v_user` 也返回 `200`。

| payload 字段 | 元数据类型 | 已验证查询接口 |
| --- | --- | --- |
| `locations` / `citys` | `comtree`，`type_data=city` | `GET /rest/city/list` |
| `industrys` | `comtree`，`type_data=industry` | `GET /rest/industry/list` |
| `functions` | `comtree`，`type_data=function` | `GET /rest/function/list` |
| `channel` | `comtree` / channel source | `GET /rest/channel/comtree/list` |
| `owner` | `foreignkey`，`type_data=user` | `GET /rest/data/userlist` |
| `folders` | folder tree | `GET /rest/folder/list?type=candidate` |
| `candidateexperience_set[].client` | company autocomplete | `GET /rest/data/autocomplete?demandKeys=["people_count","city"]&use_hide_generated=1&type=client&name=<query>&sort_func=company_suggestion` |
| `candidateexperience_set[].client` | company exact-ish list | `GET /rest/client/list?company_name=<query>` |
| `candidateexperience_set[].department` | client department | `GET /rest/clientdepartment/listdepartment?client=<client_id>` |
| `candidateexperience_set[].department` | client department tree/list | `GET /rest/clientdepartment/list_tree?client=<client_id>` 或 `GET /rest/clientdepartment/list?client=<client_id>` |
| `candidateproject_set` | `reverse_foreignkey`，`type_data=candidateproject` | 项目经历子表提交结构暂不实现，仍待补 |
| `candidateeducation_set` | `reverse_foreignkey`，`type_data=candidateeducation` | 教育经历子表结构已确认 |

已验证返回形态：

| Endpoint | 返回形态 | 样例字段 |
| --- | --- | --- |
| `/rest/custom_field/candidate/detail?suffix=coldcall` | object | `html`、`list[]`；本次 `list.length=29` |
| `/rest/custom_field/candidate/edit/all` | array | 编辑页完整字段配置；本次 `length=77` |
| `/rest/city/list` | array tree | `id`、`label`、`parent_id`、`level`、`children`、`count` |
| `/rest/industry/list` | array tree | `id`、`label`、`parent_id`、`level`、`children`、`count` |
| `/rest/function/list` | array tree | `id`、`label`、`parent_id`、`level`、`children`、`count` |
| `/rest/channel/comtree/list` | array tree | `id`、`label`、`parent_id`、`level`、`children`、`count` |
| `/rest/data/userlist` | object | `current`、`count`、`list[]`、`pages`；`list[]` 含 `id`、`name`、`email`、`status`、`__name__` |
| `/rest/folder/list?type=candidate` | array tree | `id`、`name`、`label`、`parent_id`、`level`、`children`、`count` |
| `/rest/data/autocomplete?...type=client&name=<query>...` | array | `id`、`name`、`people_count`、`city`、`__name__` |
| `/rest/client/list?company_name=<query>` | object | `count`、`list[]`、`current`、`pages` |
| `/rest/clientdepartment/listdepartment?client=<client_id>` | array tree | `id`、`name`、`parent_id`、`level`、`children`、`__name__` |
| `/rest/clientdepartment/list_tree?client=<client_id>` | object | `count`、`list[]`、`current`、`pages` |
| `/rest/clientdepartment/list?client=<client_id>` | object | `count`、`list[]`、`current`、`pages` |

前端脚本证据：

- comtree 通用映射来自 `framework.min.js`：`city` -> `/rest/city/list`，`industry` -> `/rest/industry/list`，`function` -> `/rest/function/list`，`channel` -> `/rest/channel/comtree/list`。
- 公司输入框使用 `shared/widget/common/company-suggestion/main`，默认远程 URL 为 `/rest/data/autocomplete?demandKeys=["people_count","city"]&use_hide_generated=1&type=client&name=%QUERY&sort_func=company_suggestion`。
- 文件夹树通用 URL 为 `/rest/folder/list?type=<type>`，新增人才使用 `type=candidate`。

### 对 CLI 的用途

这个接口适合在 CLI 初始化或 dry-run 阶段缓存为本地元数据：

```text
python scripts/crm_cli.py metadata candidate --suffix coldcall --output data/cache/crm-candidate-coldcall-fields.json
python scripts/crm_cli.py candidate validate --input candidate.json --metadata data/cache/crm-candidate-coldcall-fields.json
```

可直接落地的能力：

1. 校验 payload 顶层字段是否存在于详情字段配置。
2. 校验 `radio` / `dropdown` 字段的 code 是否在枚举内。
3. 把中文 label 映射为服务端 code，例如 `泰伦职级=MC` -> `gllueext114=n73407498137465810`。
4. 根据 `reverse_foreignkey` 识别子表数组字段，避免把工作经历/教育经历误当作普通字段提交。

仍不能只靠当前合同完成的能力：

1. 项目经历 `candidateproject_set` 的提交结构。
2. 重复候选人、登录过期和无权限场景的错误响应。

## CLI 封装建议

基于本仓库现有技术栈，优先用 Python。当前已落地最小骨架 `scripts/crm_cli.py`：

```text
python scripts/crm_cli.py metadata candidate --suffix coldcall --output data/cache/crm-candidate-coldcall-fields.json
python scripts/crm_cli.py candidate validate --input candidate.json --metadata data/cache/crm-candidate-coldcall-fields.json
python scripts/crm_cli.py auth check
python scripts/crm_cli.py candidate duplicate-check --email <email> --type coldcall
python scripts/crm_cli.py lookup tree --kind city --query 上海
python scripts/crm_cli.py lookup tree --kind function --query 算法
python scripts/crm_cli.py lookup company --name 字节跳动
python scripts/crm_cli.py lookup user --query <owner-name>
python scripts/crm_cli.py lookup department --client-id <client-id> --query <department-name>
python scripts/crm_cli.py candidate compose --input draft.json --lookup-cache lookup-cache.json --output candidate.json
python scripts/crm_cli.py candidate add --input candidate.json --dry-run
python scripts/crm_cli.py candidate add --input candidate.json --dry-run --output request-summary.json
python scripts/crm_cli.py candidate add --input candidate.json --confirm-real-write --output live-summary.json
```

当前实现边界：

1. `metadata candidate`：从 `CRM_COOKIE` 读取运行时登录态，缓存候选人字段配置和枚举字典，不打印 Cookie。
2. `validate`：做本地 JSON 结构校验、cold call 表单必填校验、子表数组校验、元数据枚举校验；`--strict-fields` 可额外检查未知顶层字段。当前 cold call 必填只包括电话三选一、姓名、性别、所在城市、行业、职能、渠道、工作经历公司和职位；`owner/source/folders` 不阻断校验。
3. `auth check`：用详情元数据接口检查当前登录态，可用 `--no-cookie` 验证登录失效响应。
4. `duplicate-check`：用邮箱自动补全接口做只读重复预检，命中时返回码为 `2`。
5. `lookup tree`：只读查询并本地扁平化城市、行业、职能、渠道和候选人文件夹树，用于把中文 label 转成 ID。
6. `lookup company`：只读调用公司 autocomplete，用于把公司名转成 `candidateexperience_set[].client.id`。
7. `lookup user`：只读调用 `/rest/data/userlist`，用于把 owner 名称转成用户 ID；输出中用户邮箱会被脱敏。
8. `lookup department`：只读调用 `/rest/clientdepartment/listdepartment?client=<client-id>`，用于把工作经历部门名称转成部门 ID。
9. `candidate compose`：离线读取人工草稿和本地 lookup cache，把城市、行业、职能、渠道、文件夹、owner、公司、部门等 label 转成 CRM payload ID；不联网、不读取 Cookie、不写 CRM。`owner`、`folders` 可省略，省略时不做对应 lookup。cold call 草稿缺少 `gender/industries/functions/channel` 时使用上文默认规则；lookup 精确匹配优先，模糊命中多个时取首个。
10. `add --dry-run`：不联网、不写 CRM，只打印将要发送的 endpoint、脱敏 headers、form 结构、顶层 key、子表数量、payload 字节数、payload sha256 和脱敏联系字段摘要；可加 `--output request-summary.json` 保存同一份脱敏请求摘要。摘要中的 `Cookie` 固定显示为 `[CRM_COOKIE]`，`form.data` 固定显示为 `[REDACTED_PAYLOAD_JSON]`。
11. 真实写入已开放为显式确认路径：`candidate add` 默认仍拒绝真实写入；只有在调用方已完成 dry-run 和重复预检后，显式传入 `--confirm-real-write` 才会读取 `CRM_COOKIE` 并向 `/rest/candidate/add` 发送 POST。真实写入摘要仍脱敏 `Cookie` 和 `form.data`，只记录 payload sha256、字节数、顶层字段、子表数量、服务端 `status`、新建 candidate id 和子表记录 id。
12. 后续可继续补 import 批处理和项目经历 `candidateproject_set` 的 compose 结构。

## 仍需补证

- 保存接口重复候选人时的失败响应。
- 保存接口登录 Cookie 过期后的响应；读接口登录失效响应已确认是 `{"status": false, "message": "login required"}`。
- 新增保存接口不带 `_v` 时服务端是否接受：2026-05-26 已用混淆测试记录真实写入成功，服务端返回 `status=true` 和新建 candidate id。
- 项目经历 `candidateproject_set` 的提交结构。
