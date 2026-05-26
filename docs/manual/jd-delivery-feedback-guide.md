# JD 推荐反馈填写指南

> 给业务、猎头和招聘同学使用：在 outreach 表里把候选人反馈填清楚，让下一轮推荐更准。

---

## 目录

1. [这份反馈表是做什么的](#这份反馈表是做什么的)
2. [什么时候需要填写](#什么时候需要填写)
3. [最简单的填写方法](#最简单的填写方法)
4. [8 个反馈列怎么填](#8-个反馈列怎么填)
5. [常见场景和示例](#常见场景和示例)
6. [原因码怎么选](#原因码怎么选)
7. [填写前后对比示例](#填写前后对比示例)
8. [常见问题](#常见问题)

---

## 这份反馈表是做什么的

系统会先根据 JD 推荐一批候选人，并生成一张 outreach 表。你看完候选人后，只需要在表格最后几列补充反馈。

这些反馈不是为了考核个人判断，而是为了回答几个问题：

- 这批人里哪些真的值得推进？
- 哪些人看起来分高，但其实岗位不匹配？
- 是 JD 画像理解错了，还是评分卡权重不对？
- 下一版推荐应该放宽、收紧，还是换方向？

填得越具体，下一轮推荐就越容易改准。

---

## 什么时候需要填写

推荐在三个时间点填写：

| 时间点 | 填什么 | 目的 |
| --- | --- | --- |
| 看完推荐名单后 | 先填 `feedback_label`、`feedback_stage`、`reason_codes`、`hunter_note` | 让系统知道这批推荐准不准 |
| 实际联系候选人后 | 更新 `contacted` | 记录是否已经触达 |
| 候选人进入客户流程后 | 更新 `submitted_to_client`、`interviewed`、`offer` | 记录后续转化 |

如果你时间很少，至少填两列：

1. `feedback_label`
2. `hunter_note`

---

## 最简单的填写方法

每一行代表一个候选人。你只需要看最后 8 列：

| 列名 | 最常见填法 |
| --- | --- |
| `feedback_label` | 填 `认可`、`待定` 或 `不认可` |
| `feedback_stage` | 填你认为问题主要出在哪一步，比如 `匹配` 或 `评分卡` |
| `reason_codes` | 选 1-3 个原因码，用英文分号 `;` 分开 |
| `hunter_note` | 用中文写一句具体判断 |
| `contacted` | 已联系填 `TRUE`，没联系填 `FALSE` 或留空 |
| `submitted_to_client` | 已推荐给客户填 `TRUE`，否则填 `FALSE` 或留空 |
| `interviewed` | 已面试填 `TRUE`，否则填 `FALSE` 或留空 |
| `offer` | 已 offer 填 `TRUE`，否则填 `FALSE` 或留空 |

可以先不填所有列。比如刚看完名单，还没有联系候选人，就先填前 4 列。

---

## 8 个反馈列怎么填

### `feedback_label`

这是最重要的一列，用来表达你对这个候选人的总体判断。

| 可填值 | 什么时候用 | 示例 |
| --- | --- | --- |
| `认可` | 候选人方向基本对，值得优先推进 | 背景、岗位方向、近期经历都比较匹配 |
| `待定` | 有一些亮点，但证据不足，需要补问或再看 | 公司和方向相关，但不确定是否真正负责核心工作 |
| `不认可` | 明显不适合本 JD，不建议继续推进 | 标题像，但实际做销售/运营/纯项目管理 |

不要填“不错”“可以”“一般”这类自由文本。系统只识别 `认可`、`待定`、`不认可`。

### `feedback_stage`

这列表示你认为问题主要出在哪一步。

| 可填值 | 通俗解释 | 什么时候用 |
| --- | --- | --- |
| `画像` | 系统对 JD 要找什么人理解偏了 | JD 其实要产品负责人，系统按算法专家找 |
| `评分卡` | 评分规则或权重不合适 | 某类关键词权重太高，导致不合适的人排前面 |
| `匹配` | 候选人匹配判断不准 | 关键词命中了，但实际职责不是这个方向 |
| `报告` | 报告表达或外联角度不好 | 推荐理由没讲到业务关心点 |
| `候选人状态` | 候选人本身状态问题 | 人选已不看机会、信息过期、重复候选 |

如果不确定，优先填 `匹配`。

### `reason_codes`

这列用原因码表达“为什么认可/待定/不认可”。原因码必须用英文代码，方便系统统计。

填写规则：

- 可以留空，尤其是 `认可` 的候选人。
- 如果要填，建议填 1-3 个。
- 多个原因码用英文分号 `;` 分开。
- 不要用中文顿号、逗号或换行分隔。

示例：

```text
evidence_too_shallow; title_alias_wrong
```

### `hunter_note`

这列写给人看的。用一句中文说明你的真实判断。

好的写法：

```text
视频生成产品经历匹配，但缺少游戏场景，需要先电话确认是否做过游戏内容生产链路。
```

不好的写法：

```text
一般
```

建议写清楚三件事里的至少一件：

- 为什么认可？
- 为什么不认可？
- 下一步要确认什么？

### `contacted`

是否已经联系候选人。

| 填值 | 含义 |
| --- | --- |
| `TRUE` | 已经联系过 |
| `FALSE` | 明确还没联系 |
| 留空 | 暂时不知道或还没跟进 |

### `submitted_to_client`

是否已经把候选人推荐给客户或业务面试官。

| 填值 | 含义 |
| --- | --- |
| `TRUE` | 已经推荐给客户/业务 |
| `FALSE` | 尚未推荐 |
| 留空 | 暂时不知道 |

### `interviewed`

是否已经进入面试。

| 填值 | 含义 |
| --- | --- |
| `TRUE` | 已面试或已安排面试 |
| `FALSE` | 尚未面试 |
| 留空 | 暂时不知道 |

### `offer`

是否已经 offer。

| 填值 | 含义 |
| --- | --- |
| `TRUE` | 已 offer |
| `FALSE` | 没有 offer |
| 留空 | 暂时不知道 |

---

## 常见场景和示例

### 场景 1：候选人很匹配，值得优先联系

你看到一位候选人来自目标公司，做过类似产品，近期经历也相关。

| 列名 | 填写 |
| --- | --- |
| `feedback_label` | `认可` |
| `feedback_stage` | `匹配` |
| `reason_codes` | 留空 |
| `hunter_note` | `AI 产品和视频生成经历匹配，建议优先联系，重点确认是否做过游戏内容场景。` |
| `contacted` | `FALSE` |
| `submitted_to_client` | `FALSE` |
| `interviewed` | 留空 |
| `offer` | 留空 |

### 场景 2：看起来相关，但证据不够

候选人标题是 AI 产品经理，但简历里没有写清楚他是主负责人，还是只参与过部分项目。

| 列名 | 填写 |
| --- | --- |
| `feedback_label` | `待定` |
| `feedback_stage` | `匹配` |
| `reason_codes` | `evidence_too_shallow` |
| `hunter_note` | `标题和方向相关，但证据太浅，需要电话确认实际负责范围和团队规模。` |
| `contacted` | `FALSE` |
| `submitted_to_client` | `FALSE` |
| `interviewed` | 留空 |
| `offer` | 留空 |

### 场景 3：关键词命中了，但实际职责不对

候选人简历里有“大模型”“AI”，但实际主要做销售支持或项目协调，不是岗位需要的产品/算法/工程核心职责。

| 列名 | 填写 |
| --- | --- |
| `feedback_label` | `不认可` |
| `feedback_stage` | `匹配` |
| `reason_codes` | `keyword_hit_but_wrong_duty` |
| `hunter_note` | `只是命中 AI 关键词，实际职责偏销售支持，不符合本岗位核心要求。` |
| `contacted` | `FALSE` |
| `submitted_to_client` | `FALSE` |
| `interviewed` | 留空 |
| `offer` | 留空 |

### 场景 4：系统把岗位方向理解偏了

JD 要的是产品策略负责人，但推荐里很多都是纯算法研究员。

| 列名 | 填写 |
| --- | --- |
| `feedback_label` | `不认可` |
| `feedback_stage` | `画像` |
| `reason_codes` | `wrong_role_type; jd_profile_too_broad` |
| `hunter_note` | `本 JD 更偏产品策略，不是纯算法研究岗。候选人技术强，但岗位方向不对。` |
| `contacted` | 留空 |
| `submitted_to_client` | 留空 |
| `interviewed` | 留空 |
| `offer` | 留空 |

### 场景 5：候选人本身不错，但不看机会

候选人很匹配，你联系后发现他近期不考虑机会。

| 列名 | 填写 |
| --- | --- |
| `feedback_label` | `待定` |
| `feedback_stage` | `候选人状态` |
| `reason_codes` | `candidate_unavailable` |
| `hunter_note` | `候选人方向匹配，但本人表示近期不看机会，可 3 个月后再跟。` |
| `contacted` | `TRUE` |
| `submitted_to_client` | `FALSE` |
| `interviewed` | `FALSE` |
| `offer` | `FALSE` |

### 场景 6：候选人已推进到客户面试

候选人被业务认可，已经推荐给客户并进入面试。

| 列名 | 填写 |
| --- | --- |
| `feedback_label` | `认可` |
| `feedback_stage` | `匹配` |
| `reason_codes` | 留空 |
| `hunter_note` | `已推荐给业务，业务认可其多模态产品经验，进入面试流程。` |
| `contacted` | `TRUE` |
| `submitted_to_client` | `TRUE` |
| `interviewed` | `TRUE` |
| `offer` | `FALSE` |

---

## 原因码怎么选

原因码不用每条都填。只有当你想说明“为什么不准”或“为什么需要调整”时再填。

### JD 画像问题

| 原因码 | 什么时候选 |
| --- | --- |
| `jd_profile_too_broad` | 岗位画像太宽，什么人都被算进来了 |
| `jd_profile_too_narrow` | 岗位画像太窄，漏掉了本来应该看的候选人 |
| `wrong_role_type` | 岗位类型理解错了，比如产品岗被当成算法岗 |
| `missing_key_requirement` | 漏掉了 JD 里很关键的要求 |

### 评分卡问题

| 原因码 | 什么时候选 |
| --- | --- |
| `must_have_overloaded` | 必备条件堆太多，导致判断变形 |
| `scorecard_wrong_weight` | 权重不合理，某些能力被过度放大或低估 |
| `scorecard_missing_dimension` | 少了重要评分维度 |
| `scorecard_bad_threshold` | A/B/C 分档阈值不合理 |
| `company_pool_wrong` | 目标公司池不合适 |
| `title_alias_wrong` | 职位名称别名不合适 |

### 候选人匹配问题

| 原因码 | 什么时候选 |
| --- | --- |
| `keyword_hit_but_wrong_duty` | 关键词命中了，但实际职责不对 |
| `evidence_too_shallow` | 证据太浅，不足以支撑推荐 |
| `seniority_mismatch` | 资历不匹配，太浅或太重 |
| `recent_experience_missing` | 最近经历不相关 |
| `strong_candidate_ranked_low` | 好候选人排低了 |
| `weak_candidate_ranked_high` | 弱候选人排高了 |
| `evidence_hard_to_verify` | 证据难以核实 |

### 报告和外联问题

| 原因码 | 什么时候选 |
| --- | --- |
| `outreach_angle_weak` | 外联切入点不够好 |
| `risk_not_called_out` | 风险没有在报告里说清楚 |

### 候选人状态问题

| 原因码 | 什么时候选 |
| --- | --- |
| `candidate_unavailable` | 候选人近期不看机会 |
| `candidate_duplicate` | 候选人重复 |
| `candidate_info_stale` | 候选人信息过期 |

---

## 填写前后对比示例

### 填写前

| candidate_id | name | company | title | grade | feedback_label | feedback_stage | reason_codes | hunter_note | contacted |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1567 | Anne | 美团 | AI搜索产品经理 | A |  |  |  |  |  |

### 填写后

| candidate_id | name | company | title | grade | feedback_label | feedback_stage | reason_codes | hunter_note | contacted |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1567 | Anne | 美团 | AI搜索产品经理 | A | 认可 | 匹配 |  | 候选人方向和岗位匹配，可优先触达，需确认是否做过游戏场景。 | TRUE |

---

## 常见问题

### 必须每个候选人都填吗？

不必须。优先填你看过、判断明确、准备推进或明确不推进的人。

### `feedback_label` 和 `grade` 是一回事吗？

不是。

`grade` 是系统给的 A/B/C/淘汰。`feedback_label` 是你看完后的人工判断。比如系统给 A，但你认为不合适，就可以填 `不认可`。

### `reason_codes` 看不懂怎么办？

可以先不填，只写 `hunter_note`。但如果你能选一个原因码，后续统计会更准确。

### 不知道问题出在哪个阶段，`feedback_stage` 怎么填？

优先填 `匹配`。如果你明确觉得 JD 理解错了，填 `画像`；如果觉得分数权重不合理，填 `评分卡`。

### `TRUE/FALSE` 要大写吗？

建议大写。飞书表格里也可以显示成勾选或布尔值，但最稳妥的文本写法是 `TRUE` 或 `FALSE`。

### 猎头备注会直接发给候选人或客户吗？

不会。`hunter_note` 主要用于内部复盘和下一轮推荐校准。写的时候仍建议保持专业，不写无关个人评价。

### 如果候选人已经面试但没有 offer，怎么填？

可以这样填：

```text
contacted = TRUE
submitted_to_client = TRUE
interviewed = TRUE
offer = FALSE
```

### 如果一个候选人后来状态变了，能改吗？

可以。比如一开始填 `待定`，电话沟通后确认很匹配，可以改成 `认可`，并更新 `hunter_note` 和后续状态列。
