# 人才库云同步方案设计（2026-05-25）

## 背景

当前人才库主数据源是本地 SQLite：`data/talent.db`。多端同步已经有一套安全的 bundle 机制：

- `scripts/talent_sync.py export` 导出 zip bundle。
- `scripts/talent_sync.py verify-bundle` 校验 manifest 和 checksum。
- `scripts/talent_sync.py import` 默认 dry-run。
- `scripts/talent_sync.py import --apply --confirm "确认同步人才库"` 才写入本地库。
- `TalentDB` 已有 `sync_id`、`node_id`、`sync_conflicts`、`sync_tombstones`、`sync_imports`，能处理跨机器身份、冲突、删除标记和重复导入。

痛点是传输层仍然靠手动导出文件、复制文件、导入文件。手动流程可控但繁琐，随着多台机器和多轮 campaign 增加，容易出现漏传、重复传、导错版本和忘记 dry-run 的问题。

本方案目标是把“手动传 bundle”升级为“云端自动同步”，同时保留现有本地 SQLite 性能、离线可用性和冲突安全边界。

## 核心判断

不要直接同步 `data/talent.db` 文件。

SQLite 整库文件适合本地事务，不适合通过网盘或对象存储做多端并发同步。直接覆盖会丢失另一台机器的本地新增、删除 tombstone、冲突记录、微信时间线附件索引和导入历史。即使使用 WAL 文件一起同步，也很难保证跨机器一致性。

推荐路线是：

> 保留本地 `data/talent.db` 作为工作库，把现有 bundle 同步机制改造成云端自动推拉层。

云端只负责存储加密后的同步包、manifest 和附件，不直接承载查询、匹配、打分等业务读写。

## 目标

第一阶段目标：

1. 一条命令完成多端同步：`python scripts/talent_cloud_sync.py sync`。
2. 自动拉取云端未导入 bundle，先 dry-run，安全时自动 apply。
3. 自动导出本机新 bundle 并上传到云端。
4. 有冲突时不覆盖本地，写入 `sync_conflicts` 并输出摘要。
5. 删除通过 `sync_tombstones` 传播，避免被其他机器旧数据复活。
6. 支持微信聊天 markdown 附件。
7. 云端不保存明文敏感数据，bundle 默认加密。

非目标：

1. 不把 `data/talent.db` 放进 iCloud、Dropbox、OneDrive、飞书 Drive 等网盘直接同步。
2. 第一阶段不迁移到云数据库。
3. 第一阶段不做多人权限、Web 管理后台或在线冲突解决页。
4. 不绕过现有 `TalentDB` API 和 `talent_sync.py` 冲突规则。

## 方案选型

### 方案 A：云端 bundle 自动同步

本地仍使用 SQLite。新增一个云同步 CLI，把 bundle 自动上传和下载。

适合当前阶段。改动小，复用现有同步模型，风险可控。

优点：

- 不重写人才库核心读写逻辑。
- 保留本地快速查询、FTS、向量表和离线能力。
- 与现有 `sync_id`、冲突、tombstone、附件机制兼容。
- 云端服务可以非常简单，只需要对象存储。

缺点：

- 第一版仍可能是全量 bundle，库大以后上传下载成本较高。
- 冲突解决仍在本地 CLI/数据库里，不是可视化工作台。
- 云端不能直接执行查询和推荐。

### 方案 B：云端增量事件日志

本地新增 `sync_outbox` 或 `sync_change_log`，每次写候选人、详情、评分、删除都记录变更事件。云端保存增量事件，本地按 cursor 拉取和应用。

适合第二阶段。体验更好，但需要补数据模型、事件序列化和恢复逻辑。

优点：

- 同步包小，速度快。
- 更接近实时同步。
- 可以精确知道每次变更来自哪个操作。

缺点：

- 需要改造所有写库路径，确保每个写操作都可靠记录事件。
- 需要处理事件重放、压缩、快照和乱序问题。
- 测试成本明显高于方案 A。

### 方案 C：中心化云数据库

把主库迁移到 Postgres、Supabase、Neon 或自建 API，所有端直接读写云数据库，本地只做缓存。

适合未来产品化，不适合作为当前第一步。

优点：

- 多人协作、权限、审计和 Web 后台更自然。
- 云端可直接运行查询、推荐和报表。

缺点：

- 需要重构 `TalentDB` 存储层。
- SQLite FTS、sqlite-vec、事务和本地脚本能力要重新设计。
- 离线能力和本地 campaign 工作流会变复杂。
- 迁移风险高，不解决当前“手动传文件麻烦”的最小问题。

## 推荐方案

推荐先做方案 A：云端 bundle 自动同步。

架构：

```text
本机 A data/talent.db
  -> talent_cloud_sync push
  -> 加密 bundle
  -> 云端对象存储
  -> talent_cloud_sync pull
  -> 本机 B data/talent.db

本机 B 写入后同样生成 bundle 回传云端。
```

云端目录建议：

```text
talent-sync/
  manifests/
    global.json
    nodes/<node_id>.json
  bundles/
    <created_at>-<node_id>-<bundle_id>.zip.enc
  attachments/
    optional/
  locks/
    global.lock
```

`global.json` 记录：

- 当前 schema 版本。
- 已知 node 列表。
- bundle 索引。
- 每个 bundle 的 hash、大小、创建时间、source_node_id。
- 最近一次 compact snapshot。

`nodes/<node_id>.json` 记录：

- 本机 node_id。
- 最近 push 时间。
- 最近导出的 bundle_id。
- 本机已知导入位置。
- 可选设备名。

本地新增状态文件：

```text
data/sync/cloud-state.json
```

记录：

- cloud provider。
- bucket/container/path。
- 已下载 bundle 列表。
- 已成功 apply 的云端 bundle 列表。
- 最近一次成功 sync 时间。
- 最近一次冲突摘要。

## 命令设计

第一版 CLI：

```bash
python scripts/talent_cloud_sync.py status
python scripts/talent_cloud_sync.py pull
python scripts/talent_cloud_sync.py push
python scripts/talent_cloud_sync.py sync
python scripts/talent_cloud_sync.py doctor
```

### status

只读展示：

- 本机 `node_id`。
- 本地候选人数。
- 云端 manifest 是否可读。
- 云端是否有未导入 bundle。
- 本地是否存在 open conflicts。
- 最近一次同步时间。

### pull

流程：

1. 读取云端 manifest。
2. 找出本机未导入 bundle。
3. 下载 bundle。
4. 校验加密签名、解密、verify-bundle。
5. 对每个 bundle 执行 dry-run。
6. 如果无冲突且符合自动 apply 策略，执行 apply。
7. 如果有冲突，停止自动 apply，输出冲突摘要。

默认策略：

- `created/merged/skipped/tombstoned` 可以自动 apply。
- `sync_conflicts` 新增时停止，要求用户处理。
- 来自本机 node_id 的 bundle 默认跳过，避免自导入。

### push

流程：

1. 先检查本地 open conflicts；有 open conflicts 时默认拒绝 push。
2. 导出 bundle。
3. verify-bundle。
4. 加密 bundle。
5. 上传到云端。
6. 用条件写入更新 manifest，避免并发覆盖。

默认要求：

- push 前建议自动执行一次 pull。
- 如果云端 manifest 版本在本地读取后发生变化，重新 pull 再 push。

### sync

组合命令：

```text
doctor -> pull -> push -> status
```

日常使用只需要运行：

```bash
python scripts/talent_cloud_sync.py sync
```

## 云端存储选择

### 推荐：S3 兼容对象存储

可选 Cloudflare R2、阿里 OSS、AWS S3、MinIO。

推荐原因：

- 支持对象 hash/etag。
- 支持条件写入或版本控制，适合 manifest 乐观锁。
- 对大 bundle 和附件更友好。
- 后续可平滑接入服务端 API。

配置示例：

```env
TALENT_SYNC_PROVIDER=s3
TALENT_SYNC_BUCKET=talent-agent-sync
TALENT_SYNC_PREFIX=talent-sync/prod
TALENT_SYNC_ENDPOINT=https://<account>.r2.cloudflarestorage.com
TALENT_SYNC_ACCESS_KEY_ID=...
TALENT_SYNC_SECRET_ACCESS_KEY=...
TALENT_SYNC_ENCRYPTION_KEY=...
```

### 备选：飞书 Drive

优点是已经在项目里使用飞书生态，配置心智成本低。

限制：

- 更像文件盘，做 manifest 并发锁不如 S3 自然。
- API 版本和 CLI 参数有历史漂移记录。
- 大文件、频繁覆盖和条件写入能力需要额外验证。

适合作为临时 MVP，不建议作为长期同步底座。

### 备选：自建 VPS + API

适合后续多人产品化。

第一阶段不推荐，因为需要同时维护服务端、鉴权、备份、部署和监控。

## 加密和敏感数据

人才库包含候选人姓名、联系方式、履历、微信聊天索引和平台来源。云端 bundle 必须默认加密。

建议：

1. 使用对称加密，例如 age、Fernet 或 libsodium secretbox。
2. `TALENT_SYNC_ENCRYPTION_KEY` 只存在本机 `.env` 或系统 keychain，不写入仓库。
3. 加密前先生成 manifest 和 checksum；加密后再生成云端对象 hash。
4. 云端对象命名不包含候选人姓名、公司名、手机号、微信号。
5. 日志只打印 bundle id、计数、hash，不打印候选人敏感字段。

## 冲突处理

第一版不做云端合并逻辑。所有合并仍在本地 `TalentDB.apply_sync_import()` 中完成。

规则：

- 空字段可被远端补齐。
- 非空字段冲突写入 `sync_conflicts`。
- `source_profiles` 只追加或按稳定键合并，不静默覆盖来源。
- `match_scores` 同一稳定键差异写冲突。
- `candidate_details.raw_data` 按 namespace 合并，同 key 差异写冲突。
- 删除通过 `sync_tombstones` 传播，避免旧 bundle 复活已删除候选人。

CLI 输出示例：

```text
云同步完成：
- 拉取 bundle：3
- 写入候选人：created=12, merged=48, skipped=0
- 删除传播：2
- 新增冲突：4
- 上传本机 bundle：1

存在 open conflicts，后续 push 已跳过。请先处理 sync_conflicts。
```

## 附件同步

微信聊天 markdown 归档仍保存在本地 `data/wechat-timelines/`。第一版可以继续复用 `--include-wechat-files` 打包。

规则：

- 只允许打包数据库旁 `data/wechat-timelines/` 内的 markdown。
- 导入时恢复到目标库旁的 `data/wechat-timelines/`。
- 附件路径不能包含候选人敏感信息以外的本机绝对路径。
- 附件 hash 写入 manifest，导入前校验。

后续如果附件变大，可从 bundle 内迁出为独立加密对象：

```text
attachments/<timeline_sync_id>/<sha256>.md.enc
```

## 同步时机

第一版建议手动触发为主：

- 每天开始工作前运行一次 `sync`。
- 每次重要写库后运行一次 `sync`。
- 换机器前运行一次 `sync`。

第二阶段再加自动化：

- app 启动时自动 `pull --dry-run`。
- 关闭前提醒 `push`。
- 每小时后台 `status`，不自动 apply。
- 只在无冲突时自动同步。

## 失败恢复

必须保证任一步失败都不会损坏本地库。

失败场景和处理：

| 场景 | 处理 |
| --- | --- |
| 云端不可达 | 本地继续工作，记录 `cloud_unavailable` |
| bundle 下载不完整 | checksum 失败，不导入 |
| 解密失败 | 停止，提示 key 不匹配 |
| verify-bundle 失败 | 停止，保留证据 |
| dry-run 有冲突 | 不自动 apply，写冲突摘要 |
| apply 中断 | 依赖 SQLite 事务回滚；下次根据 `sync_imports` 去重 |
| manifest 并发更新 | 重新拉取 manifest，重新计算 push |
| 本地 open conflicts | 默认禁止 push，避免扩散未解决冲突 |

## 实施阶段

### Phase 1：云端 bundle 自动同步

新增：

- `scripts/talent_cloud_sync.py`
- 云端 provider 抽象：`LocalFsProvider`、`S3Provider`
- 配置读取：`.env` / 环境变量
- 加密/解密 helper
- 云端 manifest 读写
- `status/pull/push/sync/doctor` CLI
- 测试 fixture：本地临时目录模拟云端对象存储

复用：

- `scripts/talent_sync.py export_bundle`
- `scripts/talent_sync.py verify_bundle`
- `scripts/talent_sync.py import_bundle`
- `TalentDB.apply_sync_import`

验收：

- 两个临时 SQLite 库通过本地模拟云端同步成功。
- A 端新增候选人，B 端 `sync` 后可查到。
- B 端删除候选人，A 端 `sync` 后不会复活。
- 两端同一字段冲突写入 `sync_conflicts`。
- 重复运行 `sync` 幂等。
- 加密 key 错误时不会导入。

### Phase 2：增量 bundle

新增：

- `sync_export_cursors`
- `sync_change_log` 或基于 `sync_updated_at` 的增量导出
- 定期 compact snapshot
- 云端 manifest cursor

目标：

- 大库同步从全量 zip 变成小增量。
- 保留全量 snapshot 作为恢复点。

### Phase 3：云端协作服务

新增：

- API 服务。
- 用户权限。
- Web 冲突解决页。
- 审计日志。
- 自动备份和恢复点。

只有当多用户协作成为真实需求时再进入 Phase 3。

## 推荐 MVP

第一版只做：

1. S3/R2/OSS/MinIO provider。
2. LocalFs provider 用于测试和本地模拟。
3. bundle 加密。
4. `status/pull/push/sync/doctor`。
5. 无冲突自动 apply，有冲突停止。
6. 继续使用现有全量 bundle。

暂不做：

1. 飞书 Drive provider。
2. 增量 change log。
3. Web UI。
4. 自动后台常驻进程。
5. 云端直接查询。

## 待确认问题

1. 云端落点选择：S3/R2/OSS/MinIO、飞书 Drive，还是自建 API。
2. 是否要求默认自动 apply 无冲突 bundle，还是所有 pull 都只 dry-run。
3. 加密 key 放在哪里：`.env`、macOS Keychain、1Password，还是手动输入。
4. 是否需要同步 `data/wechat-timelines/` 附件，还是第一版只同步 SQLite 内索引。
5. 是否允许后台定时同步，还是只允许手动命令触发。

## 结论

最稳妥的路线是：第一阶段做“云端 bundle 自动同步”，不要直接同步 SQLite 文件，也不要立刻迁移云数据库。

这样可以复用现有 `talent_sync.py` 和 `TalentDB` 的安全能力，把主要痛点从“手动导出/复制/导入文件”降到“一条 sync 命令”，同时保留冲突可追踪、删除可传播、敏感数据可加密和本地工作流不被打断的边界。
