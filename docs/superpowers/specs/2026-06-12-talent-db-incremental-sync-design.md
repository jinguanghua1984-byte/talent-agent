# Talent DB 增量同步技术设计

日期：2026-06-12
状态：已通过 brainstorming 设计确认，待 implementation plan

## 1. 背景

`data/talent.db` 已经随着 campaign、平台抓取、JD delivery 和主库合并持续变大。现有同步方案安全但偏重全量：

- `scripts/talent_sync.py export` 生成同步 bundle。
- `scripts/talent_sync.py verify-bundle` 校验 manifest 和 checksum。
- `scripts/talent_sync.py import` 默认 dry-run，`--apply --confirm "确认同步人才库"` 才写库。
- `scripts/talent_cloud_sync.py` 在 bundle 外加了一层飞书 Drive 加密上传、下载和本地 state。
- `TalentDB` 已有 `sync_id`、`sync_imports`、`sync_conflicts`、`sync_tombstones`、`sync_entity_aliases` 等同步元数据。

当前痛点不是同步语义缺失，而是日常同步仍然导出、上传、下载全量数据，库越大越慢。P1 的目标是把日常同步改成增量，同时尽量复用现有安全机制。

## 2. 已确认决策

- 协作模型：多人多设备、低频同步；通过流程避免并发写，不做实时多人协作。
- 新设备：首次或 state 丢失时仍使用一次全量 bootstrap；之后走增量。
- 增量范围：默认自动水位，同时保留手动 `--since` 和任务级/campaign 增量能力。
- 同步载体：云上同步沿用飞书 Drive；跨 PC 文件同步复用同一类 bundle。
- 增量粒度：P1 使用候选人闭包增量。某个候选人变化时，导出该候选人的完整关联数据。
- 变化判断：统一刷新候选人的 `sync_updated_at`，用它作为候选人级增量水位。
- `push` 门禁：云端存在本机未应用 bundle 时禁止 push，必须先 pull。
- `pull` 冲突：沿用现有 import 语义。字段级差异写入 `sync_conflicts`，候选人身份级严重冲突才阻断自动流程。
- 水位存储：放在本地 state 文件，按远端 node / bundle 记录；不写入业务 DB 作为跨端事实。
- 云端保留：P1 不自动清理历史 bundle 和 index。

## 3. 目标

P1 需要同时覆盖两种业务使用方式：

1. 云上同步：团队多台机器通过飞书 Drive 共享加密增量包。常规流程是开工先 `pull`，收工再 `push`，或直接 `sync`。
2. 跨 PC 文件同步：没有云端或临时搬运时，导出同样格式的增量 bundle，用 U 盘、网盘、聊天文件等方式传给另一台机器，再 dry-run/apply。

成功标准：

- 日常同步不再传完整 `data/talent.db` 或完整全量 bundle。
- 一次候选人更新、详情补充、来源补充、评分、微信时间线和删除都能被增量包覆盖。
- 重复导入同一个 bundle 幂等。
- 新设备 bootstrap 仍然简单可靠。
- 增量失败时能停在可解释状态，不破坏本地库。

## 4. 非目标

P1 不做以下事情：

- 不直接同步 `data/talent.db`、`.db-wal`、`.db-shm`。
- 不迁移到云数据库。
- 不做 CRDT、实时多人协作或高频并发写入。
- 不做行级最小 delta。
- 不做云端自动清理、压缩全量快照或增量归档策略。
- 不做可视化冲突解决 UI。
- 不绕过现有 `TalentDB` API、bundle 校验、dry-run 和确认式 apply。

## 5. 总体架构

P1 保留现有三层结构，只在每层补增量能力。

### 5.1 TalentDB 层

`TalentDB` 负责回答两个问题：

1. 哪些候选人自某个水位之后变化过。
2. 给定一批候选人，如何导出它们的完整同步闭包。

新增或收敛的内部能力：

- `touch_candidate_sync(candidate_id)`：刷新候选人的 `sync_updated_at`。
- 所有影响候选人业务事实的写入路径都调用 touch，包括候选人字段、详情、source profile、identity match、field value、微信时间线、score event、match score。
- 删除候选人继续写 `sync_tombstones`，增量导出时按 tombstone 时间水位包含删除记录。
- `export_sync_rows(candidate_sync_ids=None, since=None)` 支持全量和候选人闭包子集导出。

候选人闭包包含现有 bundle 的同步表：

- `candidates`
- `candidate_details`
- `source_profiles`
- `candidate_identity_matches`
- `candidate_field_values`
- `candidate_wechat_timelines`
- `score_events`
- `match_scores`
- `tombstones`

### 5.2 Bundle 层

`scripts/talent_sync.py` 继续负责 bundle 的生成、校验、dry-run、导入和确认式 apply。

新增行为：

- `export --mode full`：保留现有全量导出，用于 bootstrap。
- `export --mode incremental`：导出候选人闭包增量。
- `export --since <timestamp>`：手动水位导出，用于救急或跨 PC 明确范围。
- `export --candidate-sync-ids-file <path>` 或等价参数：支持任务级/campaign 生成候选人集合后导出。
- manifest 标记 `export_mode=incremental`，记录 `base_cursor`、`cursor_started_at`、`candidate_count`、`source_node_id`、`export_id` 和各表计数。

导入端尽量不区分全量和增量。只要 bundle 通过 checksum 和 schema 校验，就复用现有 import plan 和 apply 逻辑。

### 5.3 云同步层

`scripts/talent_cloud_sync.py` 继续使用飞书 Drive provider、加密 bundle、不可变 `bundle-index/*.json` 和 `bundles/*.zip.enc`。

新增或调整行为：

- `push` 默认生成增量 bundle。
- 如果本机没有可用 bootstrap/state，`push` 阻断并提示先做全量 bootstrap 或显式 `--since`。
- `push` 前扫描云端 index；只要存在本机未应用的远端 bundle，就阻断 push，要求先 pull。
- `pull` 按 index 顺序下载未应用 bundle，解密、校验、dry-run，再按现有语义 apply。
- `sync` 保持 `pull -> push` 顺序。
- 空增量时不上传 bundle，只返回 no-op 结果。

### 5.4 跨 PC 文件同步

跨 PC 文件同步不另建格式：

```bash
.venv/bin/python -m scripts.talent_sync export \
  --db data/talent.db \
  --mode incremental \
  --out data/sync/talent-sync-incremental-<timestamp>.zip

.venv/bin/python -m scripts.talent_sync verify-bundle \
  --bundle data/sync/talent-sync-incremental-<timestamp>.zip

.venv/bin/python -m scripts.talent_sync import \
  --db data/talent.db \
  --bundle data/sync/talent-sync-incremental-<timestamp>.zip

.venv/bin/python -m scripts.talent_sync import \
  --db data/talent.db \
  --bundle data/sync/talent-sync-incremental-<timestamp>.zip \
  --apply \
  --confirm "确认同步人才库"
```

重复导入依赖 `sync_imports` 幂等保护；本地 state 只用于体验和水位提示，不作为唯一事实。

## 6. 水位设计

P1 使用保守水位，宁可重复导出，也不能漏导。

本地 state 文件继续放在 `data/sync/` 下。云同步沿用并扩展 `cloud-state.json`；文件同步可以增加轻量 `file-sync-state.json`。

关键字段：

```json
{
  "schema": "talent_sync_state_v2",
  "local_node_id": "node-uuid",
  "last_successful_push_started_at": "2026-06-12T10:00:00Z",
  "applied_bundles": [
    {
      "bundle_id": "uuid",
      "source_node_id": "node-uuid",
      "created_at": "2026-06-12T10:05:00Z",
      "applied_at": "2026-06-12T10:06:00Z"
    }
  ],
  "blocked_remote_bundles": []
}
```

自动增量导出规则：

1. 读取 `last_successful_push_started_at`。
2. 使用安全回看窗口，例如 10 分钟，计算 `since = last_successful_push_started_at - safety_window`。
3. 查询 `sync_updated_at >= since` 的候选人。
4. 同时查询 `deleted_at >= since` 的 tombstone。
5. 导出候选人闭包。
6. bundle 上传和 index 上传都成功后，再推进 `last_successful_push_started_at` 到本次导出开始时间。

这样即使时间精度只有秒级，或导出期间本机又发生写入，也会通过下一次重叠导出补上。重复行由 `sync_id`、`sync_imports` 和现有 merge 逻辑吸收。

## 7. 数据流

### 7.1 首次 bootstrap

1. 源机器导出 `--mode full` bundle。
2. 目标机器 `verify-bundle`。
3. 目标机器 `import` dry-run。
4. 用户确认后 `import --apply --confirm "确认同步人才库"`。
5. 目标机器初始化本地 state，之后进入增量流程。

### 7.2 云端日常 sync

1. `pull` 扫描云端 index。
2. 下载本机未应用且非本机来源的 bundle。
3. 解密并 `verify-bundle`。
4. dry-run import。
5. 无候选人身份级阻断时 apply；字段级冲突写入 `sync_conflicts`。
6. 更新本地 applied bundle state。
7. `push` 检查云端是否仍有未应用远端 bundle。
8. 根据本地水位导出增量闭包。
9. 加密上传 bundle，再上传 index。
10. 更新本地 push 水位。

### 7.3 跨 PC 文件同步

1. 发送端导出增量 bundle。
2. 用户通过任意文件通道传输 zip。
3. 接收端 verify、dry-run、apply。
4. 接收端记录已导入 bundle；以后重复导入不重复写入。

## 8. 错误处理

- 无 state 且尝试默认增量 push：阻断，提示先 full bootstrap 或显式 `--since`。
- 云端存在未应用远端 bundle：push 阻断，提示先 pull。
- bundle checksum 或 manifest 校验失败：阻断，不写库。
- 解密失败：阻断，不写库，提示检查 key。
- 候选人身份级冲突：云端自动流程阻断，输出冲突报告；用户可按传统 dry-run/apply 流程人工处理。
- 字段级差异：沿用现有 import merge，写入 `sync_conflicts`，不中断整个导入。
- 飞书上传 bundle 成功但 index 失败：该 bundle 对其他机器不可见，下一次 push 可重新生成；P1 不做自动清理。
- 飞书 index 存在但 bundle 下载失败：pull 阻断并记录 `blocked_remote_bundles`。
- 空增量：返回 no-op，不上传空包。

## 9. 测试策略

聚焦测试覆盖：

- `TalentDB` 写入候选人字段时刷新 `sync_updated_at`。
- 写入详情、来源、identity、field value、微信时间线、score event、match score 时刷新父候选人的 `sync_updated_at`。
- 删除候选人产生 tombstone，并进入增量导出。
- `export --mode full` 保持现有行为。
- `export --mode incremental --since` 只导出变化候选人的闭包。
- 增量 bundle 导入空库和已有库都可 dry-run/apply。
- 重复导入同一增量 bundle 不重复写入。
- 云端 `push` 在存在未应用远端 bundle 时阻断。
- 云端 `pull` 可下载、解密、校验并应用增量 bundle。
- 空增量 push 不上传。
- LocalFs provider 模拟飞书 Drive，避免测试依赖真实云端。

最终验证：

```bash
.venv/bin/python -m pytest tests/test_talent_sync.py tests/test_talent_cloud_sync.py -q
.venv/bin/python -m pytest tests -q
git diff --check
```

## 10. 分阶段落地

P1a：补可靠变化水位

- 新增候选人 touch helper。
- 覆盖所有影响候选人的写库路径。
- 加测试证明关联数据更新会刷新候选人水位。

P1b：增量 bundle

- `TalentDB.export_sync_rows()` 支持候选人闭包过滤。
- `talent_sync export` 支持 `--mode incremental`、`--since` 和显式候选人集合。
- manifest 支持增量元数据。
- 更新 manual 中跨 PC 增量用法。

P1c：云端增量 sync

- 扩展 `cloud-state.json`。
- `push` 默认导出增量并做未应用远端 bundle 门禁。
- `pull` 记录 applied bundle 水位。
- 更新 `doctor/status` 输出。

P1d：回归和文档

- 更新 `docs/manual/talent-sync-guide.md` 和 `docs/manual/talent-cloud-sync-guide.md`。
- 用 LocalFs provider 跑双节点端到端测试。
- 保留 full bootstrap 操作说明。

## 11. 后续可选增强

如果后续全量 bootstrap 也变慢，再考虑：

- 周期性全量快照 + 增量保留窗口。
- 大附件、微信时间线附件单独做内容寻址和去重。
- 行级增量。
- 云端 bundle 清理策略。
- 可视化冲突处理。
- 中心化服务或云数据库。

