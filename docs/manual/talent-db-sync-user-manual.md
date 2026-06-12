# Talent DB 数据同步用户手册

> 给日常使用人才库的人看：不需要理解数据库，只要知道什么时候点同步、什么时候发同步包、看到冲突时怎么处理。

---

## 先看这一页

Talent DB 是本机的人才库文件。现在不要直接复制 `data/talent.db`，而是使用系统生成的同步包。

同步有两种常用方式：

| 方式 | 适合谁 | 怎么理解 |
| --- | --- | --- |
| 云上同步 | 多人、多设备长期共用一套人才库 | 系统把变化加密后放到飞书 Drive，大家先拉取再上传 |
| 跨 PC 文件同步 | 临时给另一台电脑、同事或备份机同步一次 | 系统生成一个 zip 同步包，你把 zip 发给对方导入 |

优先选云上同步；只有临时传给某台电脑、网络不方便、或需要人工审核同步包时，再用跨 PC 文件同步。

---

## 3 条安全规则

1. 不要直接复制 `data/talent.db`。

   直接复制数据库文件可能覆盖别人刚更新的数据，也可能把本机正在写入的数据库复制坏。

2. 第一次同步用全量，日常同步用增量。

   - 全量：把当前人才库完整打一个安全包，适合第一台电脑或新电脑初始化。
   - 增量：只同步上次之后变化的人才，适合日常使用。

3. 看到冲突先停，不要反复重试。

   冲突不是系统坏了，而是两边对同一个人的信息有不同记录。系统会保留证据，等人工判断。

---

## 什么时候该同步

| 场景 | 应该怎么做 |
| --- | --- |
| 开始一天工作 | 先云同步一次 |
| 导入一批候选人后 | 再云同步一次 |
| 补充了候选人电话、微信、评价、推荐记录 | 再云同步一次 |
| 删除或合并了重复候选人 | 再云同步一次 |
| 换电脑继续工作 | 旧电脑先同步，新电脑再同步 |
| 给同事临时传一批更新 | 导出跨 PC 增量同步包 |
| 新电脑第一次加入 | 先导入全量或先从云端拉取全量 bootstrap |

---

## 方式一：云上同步

云上同步适合长期协作。系统会自动完成这些事：

1. 先从飞书 Drive 拉取别人上传的新同步包。
2. 检查有没有冲突。
3. 没有冲突时，把远端变化合并到本机人才库。
4. 再把本机新增或修改的数据加密上传。

### 第一次由谁设置

第一次建议由技术同事或项目负责人设置：

```bash
.venv/bin/python -m scripts.talent_cloud_sync keygen
.venv/bin/python -m scripts.talent_cloud_sync init-remote --provider feishu
```

业务同学只需要确认：

- 飞书 Drive 同步目录已经建好。
- 当前电脑已经配好同步密钥。
- 不要把同步密钥发到群聊、文档或 Git。

### 第一台电脑：把本机人才库放到云端

第一台电脑要做 full bootstrap，也就是上传一次全量基础包：

```bash
.venv/bin/python -m scripts.talent_cloud_sync push --provider feishu --mode full
```

你可以理解为：先把“第一版完整人才库”放到云端，后面大家再同步变化。

### 第二台新电脑：从云端初始化

如果第二台电脑是空人才库，先拉取云端全量基础包：

```bash
.venv/bin/python -m scripts.talent_cloud_sync pull --provider feishu
```

之后日常同步用：

```bash
.venv/bin/python -m scripts.talent_cloud_sync sync --provider feishu
```

### 第二台电脑已经有本地数据怎么办

如果第二台电脑拉取云端前，自己已经有一些本地候选人，不要直接默认增量推送。这样容易漏掉旧本地数据。

安全做法是二选一：

```bash
.venv/bin/python -m scripts.talent_cloud_sync push --provider feishu --mode full
```

或者让技术同事指定明确起点：

```bash
.venv/bin/python -m scripts.talent_cloud_sync push --provider feishu --mode incremental --since 2026-06-12T00:00:00Z
```

普通用户优先使用 `--mode full`，更简单也更不容易漏。

### 日常最推荐命令

日常只需要执行：

```bash
.venv/bin/python -m scripts.talent_cloud_sync sync --provider feishu
```

也可以直接让 agent 做：

```text
帮我同步人才库
```

或：

```text
先从飞书拉取人才库最新数据，再把我本机的更新推送到飞书
```

### 正常结果怎么看

| 看到的结果 | 含义 | 是否需要处理 |
| --- | --- | --- |
| `applied` 大于 0 | 拉取并合并了别人上传的数据 | 正常 |
| `uploaded: true` | 本机变化已上传 | 正常 |
| `reason: no_changes` | 本机没有新变化，没有上传空包 | 正常 |
| `pull remote bundles before push` | 云端有你还没拉取的包 | 先执行 pull 或 sync |
| `blocked` / `conflicts` | 有冲突 | 停下来，人工确认 |

---

## 方式二：跨 PC 文件同步

跨 PC 文件同步适合这些情况：

- 临时把 A 电脑的数据给 B 电脑。
- 给同事发一个本次候选人更新包。
- 云上同步暂时不可用。
- 想先看 dry-run 结果，再决定是否写入。

文件同步只传 zip 同步包，不传 `data/talent.db`。

### 场景 A：新电脑第一次拿到完整人才库

发送端导出全量包：

```bash
.venv/bin/python -m scripts.talent_sync export \
  --db data/talent.db \
  --mode full \
  --out data/sync/talent-sync-full-20260612.zip
```

把 `data/sync/talent-sync-full-20260612.zip` 发给新电脑。

接收端先校验同步包：

```bash
.venv/bin/python -m scripts.talent_sync verify-bundle \
  --bundle data/sync/talent-sync-full-20260612.zip
```

接收端先预览，不写入：

```bash
.venv/bin/python -m scripts.talent_sync import \
  --db data/talent.db \
  --bundle data/sync/talent-sync-full-20260612.zip
```

确认预览没有问题后，再写入：

```bash
.venv/bin/python -m scripts.talent_sync import \
  --db data/talent.db \
  --bundle data/sync/talent-sync-full-20260612.zip \
  --apply \
  --confirm "确认同步人才库"
```

### 场景 B：日常只发今天的变化

比如你今天在电脑 A 上新增和修改了一批候选人，要发给电脑 B。

发送端导出增量包：

```bash
.venv/bin/python -m scripts.talent_sync export \
  --db data/talent.db \
  --mode incremental \
  --since 2026-06-12T00:00:00Z \
  --out data/sync/talent-sync-incremental-20260612.zip
```

接收端仍然按三步走：

```bash
.venv/bin/python -m scripts.talent_sync verify-bundle \
  --bundle data/sync/talent-sync-incremental-20260612.zip
```

```bash
.venv/bin/python -m scripts.talent_sync import \
  --db data/talent.db \
  --bundle data/sync/talent-sync-incremental-20260612.zip
```

```bash
.venv/bin/python -m scripts.talent_sync import \
  --db data/talent.db \
  --bundle data/sync/talent-sync-incremental-20260612.zip \
  --apply \
  --confirm "确认同步人才库"
```

### 场景 C：只同步指定候选人

如果只想同步几个人，可以准备一个文本文件，例如 `data/sync/candidate-sync-ids.txt`：

```text
candidate-abc123
candidate-def456
candidate-ghi789
```

导出时指定这个文件：

```bash
.venv/bin/python -m scripts.talent_sync export \
  --db data/talent.db \
  --mode incremental \
  --candidate-sync-ids-file data/sync/candidate-sync-ids.txt \
  --out data/sync/talent-sync-selected-candidates.zip
```

这种方式适合“只把本轮确认的候选人发给同事”，不适合第一次初始化新电脑。

---

## 具体例子

### 例子 1：公司电脑和家里电脑同步

早上在公司电脑：

```bash
.venv/bin/python -m scripts.talent_cloud_sync sync --provider feishu
```

白天导入了 80 个候选人，收工前再同步：

```bash
.venv/bin/python -m scripts.talent_cloud_sync sync --provider feishu
```

晚上回家，在家里电脑先同步：

```bash
.venv/bin/python -m scripts.talent_cloud_sync sync --provider feishu
```

这样家里电脑就能拿到公司电脑白天新增的候选人。

### 例子 2：同事临时给你发一个候选人包

同事发来：

```text
talent-sync-incremental-20260612.zip
```

你不要直接解压。按顺序执行：

```bash
.venv/bin/python -m scripts.talent_sync verify-bundle --bundle talent-sync-incremental-20260612.zip
```

```bash
.venv/bin/python -m scripts.talent_sync import --db data/talent.db --bundle talent-sync-incremental-20260612.zip
```

看预览没问题后：

```bash
.venv/bin/python -m scripts.talent_sync import \
  --db data/talent.db \
  --bundle talent-sync-incremental-20260612.zip \
  --apply \
  --confirm "确认同步人才库"
```

### 例子 3：你删除了重复候选人

你在电脑 A 合并或删除了重复候选人。同步后，电脑 B 也应该知道这个人已经被删除或合并。

如果用云同步：

```bash
.venv/bin/python -m scripts.talent_cloud_sync sync --provider feishu
```

如果用文件同步：

```bash
.venv/bin/python -m scripts.talent_sync export \
  --db data/talent.db \
  --mode incremental \
  --since 2026-06-12T00:00:00Z \
  --out data/sync/talent-sync-delete-records-20260612.zip
```

删除和合并记录会跟着同步包走，不需要手工告诉对方删谁。

---

## 冲突怎么理解

冲突通常有两类。

### 字段冲突

同一个候选人在两台电脑上都有记录，但字段不同。

例子：

| 字段 | 电脑 A | 电脑 B |
| --- | --- | --- |
| 城市 | 上海 | 北京 |
| 当前公司 | 字节跳动 | 火山引擎 |

这种冲突通常不会阻止同步写入。系统会记录到 `sync_conflicts`，之后由人工决定哪个更准确。

### 身份冲突

一个远端候选人可能匹配到本机多个候选人，系统无法判断到底是哪一个人。

这种冲突会阻塞自动写入。处理方式：

1. 停止继续同步。
2. 查看冲突摘要。
3. 人工确认应该合并到哪个候选人，或保留为新人。
4. 处理后再同步。

---

## 不同角色怎么用

### 业务同学

记住两个动作：

```text
开工先同步，收工再同步。
```

日常命令：

```bash
.venv/bin/python -m scripts.talent_cloud_sync sync --provider feishu
```

### 项目负责人

重点确认：

- 第一台电脑已经做过 full bootstrap。
- 新加入电脑是否已经有本地数据。
- 有本地数据的新电脑第一次上传要用 full 或明确 `--since`。
- 有冲突时不要让成员反复重试。

### 技术同事

重点维护：

- 飞书 Drive 同步目录。
- 加密 key。
- 每台电脑的环境配置。
- 冲突处理和必要时的 dry-run / apply。

---

## 常见问题

### Q1：为什么不能直接复制 `data/talent.db`？

因为它是系统内部数据库。直接复制可能覆盖别人的更新，也可能复制到半写入状态。同步包会做校验、去重、冲突记录和删除传播，更安全。

### Q2：全量同步是不是以后都不用了？

不是。第一次初始化、新电脑加入、或者已有本地数据的新电脑需要安全合并时，仍然可能需要 full bootstrap。日常高频使用才优先增量。

### Q3：增量同步会不会漏掉删除记录？

正常不会。删除、合并重复候选人会生成删除记录，同步包会把删除记录带到另一台电脑。

### Q4：重复导入同一个同步包会怎样？

系统会识别已经导入过的 bundle，不会重复创建同一批候选人。

### Q5：没有变化时云同步为什么没有上传文件？

这是正常的。增量 push 发现没有变化时会返回 no-op，不上传空包。

### Q6：看到 `pull remote bundles before push` 怎么办？

说明云端已有别人上传的新包，你本机还没有拉取。先执行：

```bash
.venv/bin/python -m scripts.talent_cloud_sync pull --provider feishu
```

或者直接：

```bash
.venv/bin/python -m scripts.talent_cloud_sync sync --provider feishu
```

### Q7：看到 `blocked` 或 `conflicts` 怎么办？

停止操作，把冲突摘要发给项目负责人或技术同事。不要直接重试，也不要直接复制 `talent.db` 覆盖。

---

## 一句话流程

日常云同步：

```bash
.venv/bin/python -m scripts.talent_cloud_sync sync --provider feishu
```

新电脑第一次：

```bash
.venv/bin/python -m scripts.talent_cloud_sync pull --provider feishu
```

跨 PC 发增量包：

```bash
.venv/bin/python -m scripts.talent_sync export --db data/talent.db --mode incremental --since 2026-06-12T00:00:00Z --out data/sync/talent-sync-incremental-20260612.zip
```

导入别人发来的同步包：

```bash
.venv/bin/python -m scripts.talent_sync verify-bundle --bundle <同步包.zip>
.venv/bin/python -m scripts.talent_sync import --db data/talent.db --bundle <同步包.zip>
.venv/bin/python -m scripts.talent_sync import --db data/talent.db --bundle <同步包.zip> --apply --confirm "确认同步人才库"
```

