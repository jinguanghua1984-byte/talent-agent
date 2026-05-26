# Current Task Ledger

> 这个文件只保存当前活跃任务、未完成项、最近完成摘要和归档索引。完整历史见 `tasks/archive/`。

## Active Task

- [x] Agent skill 分层和 Claude Code adapter 补齐（2026-05-27）：把根目录两个业务入口 skill 迁移到 `agents/skills/`，补齐 Claude Code 适配入口，并同步测试和文档。
  - [x] Plan：实施计划写入 `docs/superpowers/plans/2026-05-27-agent-skills-claude-adapters.md`；边界为 skill 文档迁移、Claude adapter、架构/skill 测试、README 和任务记录，不改业务脚本、不写 `data/talent.db`、不访问飞书。
  - [x] Verify Plan：实施前确认待修改文件为 `agents/skills/`、`.claude/skills/`、`agents/workflows/jd-talent-delivery/AGENT.md`、`tests/test_agent_architecture.py`、两个 skill 测试、`README.md`、`agents/README.md` 和任务记录；验证方式为红灯测试、聚焦测试、全量 `.venv/bin/python -m pytest tests scripts -q` 和 `git diff --check`。
  - [x] 先补失败测试，固定 `agents/skills` 和 Claude adapter 合同。
  - [x] 迁移两个 canonical skill contract 并同步引用。
  - [x] 补齐 Claude Code adapter 和说明文档。
  - [x] 运行聚焦、全量验证和 diff hygiene。
  - [x] 写入 Review 并归档完整记录。
  - Review：已新增 `docs/superpowers/plans/2026-05-27-agent-skills-claude-adapters.md`，并把 canonical skill contract 从根目录 `skills/` 迁移到 `agents/skills/`。新增 `.claude/skills/maimai-talent-search-campaign/SKILL.md`，强化 `.claude/skills/jd-talent-delivery/SKILL.md`，让 Claude Code adapter 先读 `agents/capabilities.md`、再读 canonical skill、最后读 canonical workflow；同步更新 `README.md`、`agents/README.md`、`agents/adapters/claude-code/README.md`、相关 workflow 引用和架构/skill 测试。红灯验证：迁移前聚焦测试 `17 failed, 7 passed`，失败点覆盖缺少 `agents/skills`、缺少 maimai Claude adapter、README 未声明新层级和 maimai workflow 缺少触发入口；修复后聚焦测试 `24 passed`，全量 `.venv/bin/python -m pytest tests scripts -q` -> `907 passed, 1 warning`，warning 为既有 `scripts/test_boss.py` event loop deprecation；`git diff --check` 通过。边界：未改业务脚本，未写 `data/talent.db`，未访问飞书；历史 `docs/superpowers/` 计划/规格中的旧路径保留为历史记录。

- [x] 脚本清理优化计划文档（2026-05-26）：把一次性脚本审查结论整理为可执行实施计划并保存。
  - [x] Plan：基于脚本审查结论和当前代码引用，输出 `docs/superpowers/plans/2026-05-26-script-cleanup-and-hygiene.md`；只写计划和任务记录，不删除、不移动、不重构任何脚本。
  - [x] Verify Plan：修改边界限定为计划文档、任务台账和归档记录；验证方式为计划占位符/冲突标记扫描、关键证据扫描和 `git diff --check`。
  - [x] 写入脚本清理实施计划。
  - [x] 运行计划自检并归档任务记录。
  - Review：已新增 `docs/superpowers/plans/2026-05-26-script-cleanup-and-hygiene.md`，共 742 行。计划把脚本清理拆成 7 个任务：脚本清单和护栏基线、`scripts/test_*.py` 迁移到 `tests/`、删除已有替代的 `score_candidates.py`、审批后删除 Hunyuan ABC 一次性任务脚本、将 `data-manager.py` 改成 importable module + 兼容 shim、保留并标记 `maimai_ai_infra_*` legacy compatibility layer、最终全量验证和任务归档。计划明确 `hunyuan_abc_*` 删除必须先征得用户确认，`maimai_ai_infra_*` 第一阶段不删除，因为仍被 orchestrator 和回归测试引用。本轮未删除、移动或重构任何脚本，未写 `data/talent.db`，未访问飞书。验证：占位符/冲突标记扫描无命中；关键证据扫描覆盖 `scripts/test_boss.py`、`hunyuan_abc_detail_tasks.py`、`hunyuan_abc_parallel_supervisor.ps1`、`score_candidates.py`、`maimai_campaign_orchestrator.py`、`data-manager.py` 和 `maimai_ai_infra_search_plan.py`；新计划文件 `git diff --no-index --check /dev/null docs/superpowers/plans/2026-05-26-script-cleanup-and-hygiene.md` 无 whitespace 输出，`git diff --check -- tasks/todo.md tasks/archive/2026-05.md` 通过。计划文档任务未运行 pytest。

- [x] 本机人才库同步到飞书（2026-05-26）：执行真实飞书云同步，验证远端加密 bundle 结构和重复同步幂等。
  - [x] Plan：使用已初始化的本机 `.env` 和飞书 Drive 目录执行 `scripts.talent_cloud_sync sync`；只上传 Fernet 加密 bundle/index，不上传 `data/talent.db`；同步后核对远端 `bundle-index` 和 `bundles`；若重复同步暴露幂等问题，先用测试复现再修复。
  - [x] Verify Plan：验证方式为真实 `sync` 输出、飞书端文件列表、聚焦云同步测试、py_compile 和 `git diff --check`；密钥不输出到聊天或任务记录。
  - [x] 完成首次真实飞书同步并确认候选人/详情/source profile 计数。
  - [x] 读取第二次 `sync` 校验结果，发现重复上传新 bundle。
  - [x] 用失败测试固定“逻辑数据库未变化时不重复上传”的幂等要求。
  - [x] 修复云同步数据库指纹，避免 raw SQLite 文件字节变化导致重复上传。
  - [x] 重新执行飞书同步幂等验证、远端文件核对和测试。
  - [x] 写入 Review 并归档完整记录。
  - Review：已把本机人才库同步到飞书 Drive 根目录 `Talent Agent Sync`。真实同步只上传加密 bundle 分片和 index，不上传 `data/talent.db`。首次同步成功上传 bundle `3b06badc-9ccc-4531-83fb-6a9c13f7c0b0`，包含 `candidates=20013`、`candidate_details=20013`、`source_profiles=20013`。第二次旧版幂等校验暴露 raw SQLite 文件哈希不稳定导致重复上传，产生 bundle `c8ab43fd-964e-4ff1-9f2b-224284685711`；已按 TDD 修复为基于同步导出内容的语义指纹，并迁移本机 cloud-state。修复后真实 `sync` 返回 `pull.skipped=2`、`push.uploaded=false`、`reason=unchanged`，远端保持 `bundle-index=2`、加密分片 `bundles=12`，没有第三次上传。已补充同步工作目录清理和 `.gitignore` 的 `data/sync/`，并删除本机明文临时 zip，只保留 `cloud-state.json`。`doctor` 返回 `ok=true`，飞书 quota API `90007001` 继续作为 warning，不阻断同步。验证：`.venv/bin/python -m pytest tests/test_talent_cloud_sync.py -q` -> `25 passed`；`.venv/bin/python -m pytest tests scripts -q` -> `906 passed, 1 warning`；py_compile 和 `git diff --check` 通过。

- [x] 人才库云同步密钥和本机飞书配置初始化（2026-05-26）：引导并完成本机 `.env`、飞书 Drive 根目录和同步目录初始化。
  - [x] Plan：检查 `lark-cli` 鉴权、`.gitignore`、现有 `.env` 和云同步 CLI 配置读取方式；创建或复用飞书 Drive 根文件夹；生成 Fernet 同步密钥并写入本机 `.env`；初始化远端目录；不执行真实 push/sync，不上传 `data/talent.db`。
  - [x] Verify Plan：验证 `.env` 权限和忽略状态、CLI 可读取本地 `.env`、飞书目录结构存在、`doctor/status` 可运行、聚焦测试和 py_compile 通过。
  - [x] 修复 CLI 入口读取 `.env` 的问题，并补测试。
  - [x] 创建飞书 Drive 根文件夹 `Talent Agent Sync`。
  - [x] 生成同步密钥并写入本机 `.env`，密钥未输出到聊天。
  - [x] 初始化飞书同步子目录。
  - [x] 修复真实 `lark-cli` 返回包装和容量检查兼容问题，并补测试。
  - Review：本机 `.env` 已新增 `TALENT_SYNC_PROVIDER=feishu`、飞书根目录 token、`TALENT_SYNC_FEISHU_AS=user`、同步状态/工作目录、自动 apply 开关和 Fernet 同步密钥；`.env` 权限为 `rw-------` 且被 `.gitignore` 忽略。已创建飞书 Drive 根文件夹 `Talent Agent Sync`，链接为 `https://sq8org1v4k6.feishu.cn/drive/folder/LtI3f0lKql7RUWdOB8CcQ5CInOb`；远端目录已初始化，包含 `_meta/nodes`、`bundle-index`、`bundles`、`attachments`、`locks`、`tmp`。`status` 返回 `provider=feishu`、本机 `node_id=04e781c4-2c3e-40a3-8ca9-1f8df02c562f`、候选人 `20013`、已应用 bundle `0`。`doctor` 返回 `ok=true`，容量 API 当前因飞书 `quota_details` 接口返回 `90007001` 被降级为 warning，不阻断同步配置。安全边界：未执行 `push/sync`，未上传 raw SQLite，未打印同步密钥。验证：`.venv/bin/python -m pytest tests/test_talent_cloud_sync.py -q` -> `22 passed`；`.venv/bin/python -m py_compile scripts/talent_cloud_sync.py scripts/talent_cloud_sync_providers.py` 通过；`git diff --check -- scripts/talent_cloud_sync.py scripts/talent_cloud_sync_providers.py tests/test_talent_cloud_sync.py` 通过。

- [x] 人才库云端同步非技术使用指南（2026-05-26）：在 `docs/manual/` 写一份面向非技术人士的云同步操作指南。
  - [x] Plan：参考现有 `docs/manual/talent-sync-guide.md`、云同步 CLI 和飞书 Drive P1 边界，新增独立手册；不改业务逻辑、不写 `data/talent.db`、不访问真实飞书 Drive。
  - [x] Verify Plan：待修改文件限定为 `docs/manual/talent-cloud-sync-guide.md`、任务台账和可选手册索引；验证方式为文档可读性自检、关键安全边界扫描、占位符/冲突标记扫描和 `git diff --check`。
  - [x] 写入非技术用户指南。
  - [x] 自检并归档任务记录。
  - Review：已新增 `docs/manual/talent-cloud-sync-guide.md`，共 292 行，面向业务、猎头和招聘同学说明人才库云端同步。文档覆盖同步目的、3 条核心规则、加密同步包工作方式、首次配置职责、日常同步话术、多人协作顺序、正常状态含义、冲突处理和常见问题。安全边界明确：不要手动上传/覆盖 `data/talent.db`，不要把同步密钥发群聊/写文档/提交 Git，飞书空间满时不要手删 `bundles` 或 `bundle-index`，冲突时只读查看并停止自动写库。本轮只写 Markdown 和任务记录，未访问真实飞书 Drive，未写 `data/talent.db`，未改业务逻辑。验证：`.venv/bin/python -m scripts.talent_cloud_sync --help` 通过；关键术语扫描覆盖 `sync --provider feishu`、`doctor --provider feishu`、`init-remote --provider feishu`、`data/talent.db`、冲突和加密；`rg -n "TBD|TODO|<<<<<<<|=======|>>>>>>>|待补|占位|implement later|fill in" docs/manual/talent-cloud-sync-guide.md` 无命中；`git diff --check -- docs/manual/talent-cloud-sync-guide.md tasks/todo.md tasks/archive/2026-05.md` 通过。

- [x] 飞书 Drive 版人才库云同步 P1 实现（2026-05-26）：按实施计划开发 Feishu Drive provider 云同步，完成后发飞书通知。
  - [x] Plan：执行 `docs/superpowers/plans/2026-05-26-feishu-drive-talent-cloud-sync-p1.md`；实现边界为新增云同步 CLI/provider/tests，更新依赖、手册和任务记录；不上传 raw SQLite、不写 `data/talent.db`、测试不创建真实飞书目录。
  - [x] Verify Plan：遵守 TDD，先用 `tests/test_talent_cloud_sync.py` 红灯验证缺失模块和 Feishu init 行为，再实现；验证方式为聚焦云同步测试、`tests/test_talent_sync.py` 回归、py_compile、全量 pytest、diff hygiene。
  - [x] 新增 `cryptography>=42.0.0` 并安装到 `.venv`。
  - [x] 新增云同步 CLI、LocalFs provider、FeishuDriveProvider、加密 bundle push/pull/sync、冲突预览阻断和状态记录。
  - [x] 拆分 provider 模块，保持主 CLI 文件不过度膨胀。
  - [x] 更新 `docs/manual/talent-sync-guide.md` 的飞书 Drive P1 使用说明。
  - [x] 执行聚焦、编译、全量验证和 diff hygiene。
  - [x] 发送飞书完成通知。
  - Review：已完成 Feishu Drive P1 云同步实现。新增 `scripts/talent_cloud_sync.py`、`scripts/talent_cloud_sync_common.py`、`scripts/talent_cloud_sync_providers.py` 和 `tests/test_talent_cloud_sync.py`；实现 Fernet 加密、LocalFs provider、FeishuDriveProvider、`keygen/status/init-remote/push/pull/sync/doctor` CLI、不可变加密 bundle + `bundle-index`、错误 key 阻断、冲突预览阻断、tombstone 传播和重复 sync 幂等。更新 `requirements.txt` 增加 `cryptography>=42.0.0`，并补充 `docs/manual/talent-sync-guide.md` 的飞书 Drive P1 使用说明。测试只使用 `tmp_path` 和 fake Feishu runner，未写 `data/talent.db`，未创建真实飞书同步目录，未上传 raw SQLite。验证：`tests/test_talent_cloud_sync.py tests/test_talent_sync.py` -> `56 passed`；全量 `.venv/bin/python -m pytest tests scripts -q` -> `899 passed, 1 warning`；py_compile 和 `git diff --check` 通过。完成通知已发 `JD需求协同`，`message_id=om_x100b6e60e50f3098b2515770c2e1dad`。

- [x] 飞书 Drive 版人才库云同步 P1 实施计划（2026-05-26）：基于已确认的 Feishu Drive provider 设计，写可执行 TDD 实施计划。
  - [x] Plan：读取 P1 设计、`talent_sync.py`、`tests/test_talent_sync.py` 和飞书 CLI 约束；输出 `docs/superpowers/plans/2026-05-26-feishu-drive-talent-cloud-sync-p1.md`，覆盖文件结构、任务拆分、TDD 步骤、命令、验收和执行方式。
  - [x] Verify Plan：本轮只新增实施计划和任务记录，不改业务代码、不写 `data/talent.db`、不访问真实飞书 Drive；验证方式为计划占位符扫描、设计覆盖自检和 `git diff --check`。
  - [x] 写入实施计划文档。
  - [x] 自检计划覆盖 P1 设计并更新任务记录。
  - Review：已新增 `docs/superpowers/plans/2026-05-26-feishu-drive-talent-cloud-sync-p1.md`，共 7 个任务：配置/加密/状态、LocalFs provider、加密 bundle push、pull/错误 key/冲突阻断、sync/tombstone/idempotence、FeishuDriveProvider/doctor、CLI/手册/最终验证。计划明确新增 `scripts/talent_cloud_sync.py` 和 `tests/test_talent_cloud_sync.py`，修改 `requirements.txt` 加 `cryptography>=42.0.0`，并在实现完成后更新 `docs/manual/talent-sync-guide.md`。计划覆盖 Feishu Drive provider、不可变 `bundle-index`、不同步 raw SQLite、冲突默认阻断、确认式写入 `sync_conflicts`、容量/scope doctor、错误 key 不导入和本地模拟双库同步验收。本轮未改业务代码、未写 `data/talent.db`、未访问真实飞书 Drive。验证：占位符/冲突标记扫描无命中；设计覆盖自检已写入计划末尾；`git diff --check -- docs/superpowers/plans/2026-05-26-feishu-drive-talent-cloud-sync-p1.md tasks/todo.md` 通过。

- [x] 飞书 Drive 版人才库云同步 P1 设计（2026-05-26）：阅读 `docs/design-discussions/2026-05-25-talent-library-cloud-sync-design.md`，把数据库云端同步 P1 收敛为飞书 Drive 云端环境。
  - [x] Plan：先读取现有云同步设计、`talent_sync.py` bundle 能力、飞书 CLI/Drive 可用命令和历史任务记录；再更新设计文档中云端选型、P1 架构、manifest/目录、CLI、权限、容量、失败恢复、验收和实施边界；最后做文档自检和 diff 检查。
  - [x] Verify Plan：修改边界限定为设计文档和任务记录，不实现代码、不写 `data/talent.db`、不创建真实飞书目录；验证方式为占位符/冲突标记扫描、关键术语扫描和 `git diff --check`。
  - [x] 更新设计文档 P1 为 Feishu Drive provider。
  - [x] 文档自检和任务记录归档。
  - Review：已更新 `docs/design-discussions/2026-05-25-talent-library-cloud-sync-design.md`。P1 从 S3/R2/OSS/MinIO 优先改为 Feishu Drive provider 优先；保留“不直接同步 raw SQLite，只同步加密 bundle”的核心原则；新增飞书 Drive 目录模型 `Talent Agent Sync/_meta/bundle-index/bundles/attachments/locks/tmp`；用不可变 bundle + 不可变 `bundle-index/*.json` 规避飞书 Drive 缺少 S3 条件写入的问题；明确不使用 `lark-cli drive +sync` 直接同步目录；补充 `lark-cli` 命令、必要 scope、容量检查、orphan bundle 修复、冲突确认式 apply、验收项和推荐 MVP。验证：`rg -n 'TBD|TODO|<<<<<<<|=======|>>>>>>>|待补|占位|implement later|fill in' docs/design-discussions/2026-05-25-talent-library-cloud-sync-design.md` 无命中；关键 P1 术语扫描通过；`git diff --check -- docs/design-discussions/2026-05-25-talent-library-cloud-sync-design.md tasks/todo.md` 通过。

- [x] 导入脉脉列表和详情 capture 到人才库（2026-05-26）：先导入 `/Users/eric/Downloads/maimai-capture-2026-05-25.json`，完成后再导入 `/Users/eric/Downloads/maimai-detail-capture-2026-05-25.json`。
  - [x] Plan：读取 `talent_library import` 与 `maimai_detail_import` 合同；列表 capture 先 dry-run，clean 后备份并 apply；详情 capture 在列表 apply 后再 dry-run，检查 matched/unmatched/failed/apply_blockers/capture_blockers，clean 后备份并 apply；最后做写后统计、完整性和报告校验。
  - [x] Verify Plan：修改边界为 `data/talent.db`、`data/output/` 导入报告和任务记录；不手写 SQL 写库、不直接复制覆盖主库；验证方式为列表 dry-run/apply JSON、详情 dry-run/apply JSON、`PRAGMA integrity_check`、关键表计数、`maimai_detail_capture` 覆盖数和 `git status --short -- data/talent.db`。
  - [x] 列表 capture dry-run 预检。
  - [x] 备份主库并执行列表 apply。
  - [x] 详情 capture dry-run 预检。
  - [x] 备份主库并执行详情 apply。
  - [x] 写后验证和任务记录。
  - Review：列表 capture dry-run/apply 均为 `raw=354/unique=354/created=132/merged=222/pending=0/errors=0`。详情原始 dry-run 为 `matched=354/unmatched=0/failed_jobs=0/capture_blockers=0/apply_blockers=1`，唯一阻断为 `platform_id=237110197`、候选人“无无”、`missing_work_experience`；按既有脚本和测试合同生成过滤副本 `data/output/maimai-detail-capture-2026-05-25-filtered-for-import.json`，记录跳过报告 `data/output/maimai-detail-2026-05-26-skipped-apply-blockers.json`，过滤后 dry-run clean，apply 写入 `353` 条详情并全部 verified。备份：`data/backups/talent-20260526-before-maimai-list-import.db`、`data/backups/talent-20260526-before-maimai-detail-import.db`。写后主库 `PRAGMA integrity_check=ok`，`candidates=20013/source_profiles_maimai=20013/candidate_details=20013/maimai_detail_capture=5802/data_level_detailed=19986/pending_merges=0/sync_conflicts=0`；`talent_sync status` 返回候选人 `20013`、导入记录 `1`。验证：`.venv/bin/python -m pytest tests/test_talent_library_cli.py tests/test_maimai_detail_import.py tests/test_talent_db.py -q` -> `142 passed`；`git diff --check -- tasks/todo.md` 通过。

- [x] 发布 JD 推荐 feedback 指南到飞书（2026-05-26）：把 `docs/manual/jd-delivery-feedback-guide.md` 导入并移动到飞书知识库 `JD需求交付`。
  - [x] Plan：先检查 `lark-cli` 鉴权；对 Markdown 执行 docx import dry-run 和 wiki move dry-run；真实导入后移动到 `space_id=7642607697183001542` 根目录；最后读回 Wiki 节点和 Doc 内容。
  - [x] Verify Plan：修改边界限于任务记录；验证方式为 `lark-cli doctor/auth status`、dry-run 成功、真实导入/移动成功、Wiki node get 和 docs fetch 读回成功、`git diff --check`。
  - [x] Dry-run 导入和 Wiki 移动。
  - [x] 真实导入、移动和读回。
  - [x] Review：已将 `docs/manual/jd-delivery-feedback-guide.md` 以 Docx 导入飞书并移动到 `JD需求交付` 知识库根目录。飞书 Wiki 链接：`https://sq8org1v4k6.feishu.cn/wiki/BEjWwIIlGifRWJkUigncAL7tnrb`；Doc 链接：`https://sq8org1v4k6.feishu.cn/docx/QEi2dqbkOo8YLzxBwDlc2ySanRh`。验证：`lark-cli doctor` 和 `lark-cli auth status` 通过；`drive +import --dry-run` 和 `wiki +move --dry-run` 通过；真实导入 ticket `7644044282513656789` 成功；wiki move task `7644044350623845306-290e50094ca80b18149d000d82822cc51f1e429b` 成功；`wiki +node-get` 读回标题 `JD推荐反馈填写指南`、`obj_type=docx`、`space_id=7642607697183001542`；`docs +fetch` 读回正文包含指南标题和 feedback 表字段。

- [x] JD 推荐 feedback 填写用户指南（2026-05-26）：在 `docs/manual/` 写一份面向纯业务人员的 outreach feedback 列填写指南，要求通俗易懂，并包含场景和示例。
  - [x] Plan：参考现有 manual 文档风格和 `jd_delivery_feedback` 字段合同，新增一份独立指南，不改业务逻辑。
  - [x] Verify Plan：待修改文件限定为 `docs/manual/jd-delivery-feedback-guide.md`、`tasks/todo.md`、`tasks/archive/2026-05.md`；验证方式为 Markdown 自检、字段名/合法值核对、占位符/冲突标记扫描和 `git diff --check`。
  - [x] 写入用户指南。
  - [x] 自检字段、场景、示例和业务可读性。
  - [x] Review：已新增 `docs/manual/jd-delivery-feedback-guide.md`，面向业务、猎头和招聘同学说明 outreach 表最后 8 个 feedback 列的填写方式。文档覆盖什么时候填、最小填写方法、每列合法值、6 个常见业务场景、原因码选择、填写前后对比和常见问题。验证：字段名和合法值与 `scripts/jd_delivery_feedback.py` 合同一致；`rg -n "TBD|TODO|<<<<<<<|=======|>>>>>>>|待补|占位" docs/manual/jd-delivery-feedback-guide.md` 无命中；`git diff --check -- docs/manual/jd-delivery-feedback-guide.md tasks/todo.md tasks/archive/2026-05.md` 通过。

- [x] JD 推荐 feedback 格式飞书 demo（2026-05-26）：用新开发的 `jd-talent-delivery` workflow 生成一版 demo 人选推荐和 outreach 表，发布到飞书，让用户查看 feedback 列的填写格式。
  - [x] Plan：使用现有标准 JD 做小规模 demo 推荐；生成独立 `data/output/` 运行目录；在 outreach CSV 的反馈列补入少量示例值；执行飞书 dry-run、真实发布、回读和通知。
  - [x] Verify Plan：修改边界限于本次 demo 输出和任务记录，不写 `data/talent.db`，不发起新的平台搜索；验证方式为 `lark-cli doctor/auth status`、质量门禁、飞书回读、CSV feedback 列检查和主库只读状态对比。
  - [x] S0：前置检查和 demo JD 选择。
  - [x] S1-S6：生成岗位画像、评分卡、推荐报告和 outreach 表。
  - [x] Demo feedback：在 outreach 表补充示例反馈列值，并编译一份本地反馈样例。
  - [x] S7-S8：发布飞书、回读 Wiki/Doc/Sheet 并发送完成通知。
  - [x] Review：已用 `docs/business-requirements/12-tencent-games-multimodal-strategy-product-manager.md` 生成 Top10 demo 交付包，输出目录 `data/output/12-tencent-games-multimodal-strategy-product-manager-2026-05-26`。推荐质量门禁 passed，粗筛 19881 人、精排 536 人，Top10 为 `A=2/B=8/C=0/淘汰=0`。outreach 表包含并展示 8 个 feedback 列：`feedback_label`、`feedback_stage`、`reason_codes`、`hunter_note`、`contacted`、`submitted_to_client`、`interviewed`、`offer`；前两行填入 demo 示例，读回 `R1:Y3` 通过。飞书链接：Wiki `https://sq8org1v4k6.feishu.cn/wiki/YeQMw69ANivOOikdSapcnjLanDg`，JD `https://sq8org1v4k6.feishu.cn/docx/DwjndxnFeoIL0vxqJHEckZXRnMP`，岗位画像 `https://sq8org1v4k6.feishu.cn/docx/GDdydMFFkofJWmx6FXqcLy5KnGb`，推荐报告 `https://sq8org1v4k6.feishu.cn/docx/ORi6dj7Zlo3IKrxyqqDcE8hFnSh`，外联表 `https://sq8org1v4k6.feishu.cn/sheets/UjQJsnyG5hYu1Pt1rKncXKK0n5b`。本地 feedback 样例 `feedback/delivery-feedback-demo.json` 已编译为 `feedback-summary-demo.json` 和 `calibration-suggestions-demo.json`。发布时发现 Sheet 布尔值读回为 API boolean 导致 `TRUE/FALSE` 比对失败，已用 TDD 修复 `scripts/jd_talent_delivery_feishu.py` 的布尔归一化并补测试。完成通知已发 `JD需求协同`，`message_id=om_x100b6e64b451cca4b3c2c8ea302308d`。主库保持只读，`match_scores=0`。验证：`lark-cli doctor/auth status` 通过；`.venv/bin/python -m pytest tests/test_jd_talent_delivery_feishu.py tests/test_jd_delivery_feedback.py -q` -> `54 passed`；全量 `.venv/bin/python -m pytest tests scripts -q` -> `880 passed, 1 warning`；`git diff --check` 和 `py_compile` 通过。
- [x] 提交并推送全部更新（2026-05-26）：按用户要求提交当前所有非忽略工作区变更，并推送到 `origin/main`。
  - [x] Plan：先核对分支、状态、diff 范围和未跟踪文件；再运行 diff hygiene、敏感信息扫描和测试；随后 `git add -A`、复查 staged diff、提交、推送；最后核对本地与远端一致。
  - [x] Verify Plan：本次提交边界为当前工作区所有非忽略变更；不纳入 `.gstack/`、数据库、临时 Cookie/token/密码、真实候选人隐私或本地浏览器会话产物。
  - [x] Task 1：完成 scope 复查和验证。当前变更集中在 CRM 新增人才 API/CLI、脱敏研究文档、`.gstack/` 忽略、任务账本和经验记录；`git diff --check`、凭据扫描、`python -m py_compile scripts\crm_cli.py` 通过；全量 `python -m pytest tests scripts -q` -> `903 passed, 1 warning`，warning 为既有 `scripts/test_boss.py` event loop deprecation。
  - [x] Task 2：暂存全部非忽略变更并复查 staged diff。staged 范围为 9 个文件：CRM API 合同/调查文档、脱敏 payload 样例、`scripts/crm_cli.py`、`tests/test_crm_cli.py`、`.gitignore`、任务账本、经验记录和 error log；`git diff --cached --check` 通过。
  - [x] Task 3：处理远端先行提交并完成 rebase。首次 push 被拒绝，因为 `origin/main` 领先 2 个提交；已 fetch 后把本地 CRM 提交 rebase 到最新远端，保留远端飞书云同步任务记录和本地 CRM 任务记录。
  - [x] Task 4：修复 rebase 后暴露的 Windows 云同步回归。全量测试首次失败为 `talent_cloud_sync` 预览库 `preview.db` 句柄未关闭；已改为显式关闭 SQLite source/target 连接，并记录到 `memory/error-log.md`。聚焦回归 `2 passed`；合并后全量 `python -m pytest tests scripts -q` -> `930 passed, 1 warning`，warning 仍为既有 `scripts/test_boss.py` event loop deprecation。
  - [x] Task 5：推送到 `origin/main`，验证 status clean 且 ahead/behind 为 `0 0`。
  - Review：已提交并推送当前所有非忽略更新。主提交 `736cbfe Add CRM candidate add CLI` 覆盖 CRM 新增人才 API/CLI、脱敏合同文档、payload 样例、测试、`.gstack/` 忽略和任务/经验记录；追加提交 `e0bc73d Fix cloud sync preview DB cleanup` 修复 rebase 后远端云同步代码在 Windows 临时 SQLite 预览库清理时的文件句柄问题。推送前后验证：`git diff --check` 通过；凭据/隐私扫描无命中；`python -m py_compile scripts\crm_cli.py scripts\talent_cloud_sync.py` 通过；聚焦云同步回归 `2 passed`；全量 `python -m pytest tests scripts -q` -> `930 passed, 1 warning`，warning 为既有 `scripts/test_boss.py` event loop deprecation；推送后 `git status --short --branch` 为 clean，`git rev-list --left-right --count HEAD...origin/main` 为 `0 0`。

- [ ] CRM 新增人才 API 调用方式调查（2026-05-26）：在用户授权和手动登录前提下，观察 `http://101.200.132.164/crm` 新增人才流程的真实网络请求，整理可复现 API 合同，并评估 CLI 封装路径。
  - [x] Plan：先打开 CRM 并确认页面状态；再由用户手动登录/必要时接管；随后清空 network、执行一次“新增人才”；最后提取 method/path/headers/payload/response，脱敏后写出接口合同。
  - [x] Verify Plan：边界为浏览器被动观察和本地文档记录；不绕过登录、验证码、风控或权限；不把 Cookie/token/密码写入仓库；复现只使用用户已有权限的请求，并优先 dry-run 或测试数据。
  - [x] Task 1：启动 Codex App 内置 Browser，打开 CRM 入口并记录页面状态。`/crm` 302 到登录页，登录表单可见；已纠正为使用内置 Browser，不继续使用外部 gstack 会话。
  - [x] Task 2：完成用户手动登录/接管，定位“新增人才”入口。入口为顶部新增菜单 `#candidate/add`，表单已打开。
  - [x] Task 3：清空 network 后执行新增人才，捕获真实 API 请求。用户已提供 `POST /rest/candidate/add?_v=...&_v_user=300` 的 cURL；原始 Cookie 未入库，文档只保留脱敏头结构。
  - [x] Task 4：整理脱敏 API 合同和最小复现方案。已写入 `docs/research/2026-05-26-crm-candidate-add-api-investigation.md`，包含端点、保存框架证据、字段映射和待确认项。
  - [x] Task 5：评估 Python/Node CLI 封装方案和下一步实现边界。已写入 `docs/research/2026-05-26-crm-candidate-add-api-contract.md`；建议先用 Python 做 dry-run/validate/add，真实调用前补成功响应和选项查询接口。
  - [x] Task 6：捕获保存后详情页字段元数据接口。用户已提供 `GET /rest/custom_field/candidate/detail?_v=...&_v_user=300&suffix=coldcall` 和响应；已写入合同文档，记录字段配置、枚举字典、树形/外键数据源和 reverse foreign key 子表信息，原始 Cookie 未入库。
  - [x] Task 7：经用户授权打开临时 CDP Chrome，自动登录并验证 lookup 查询接口。已确认 `/rest/city/list`、`/rest/industry/list`、`/rest/function/list`、`/rest/channel/comtree/list`、`/rest/data/userlist`、`/rest/folder/list?type=candidate`、公司 autocomplete、`/rest/client/list?company_name=<query>` 和部门查询接口；账号密码未写入本地文件。
  - [x] Task 8：实现 CRM 新增人才最小 Python CLI 骨架。计划：先按 TDD 写 `metadata candidate`、`candidate validate`、`candidate add --dry-run` 的聚焦测试并确认红灯；再新增 `scripts/crm_cli.py`；最后运行聚焦测试、语法检查、脱敏扫描和 diff 检查。边界：本阶段不保存登录凭据、不实现真实写入 `--yes`，只支持元数据抓取、payload 本地校验和新增请求 dry-run 摘要。
  - CLI Review：已新增 `scripts/crm_cli.py` 和 `tests/test_crm_cli.py`。当前支持 `metadata candidate` 从 `CRM_COOKIE` 读取运行时登录态并缓存字段元数据，`candidate validate` 做本地 JSON/必填/子表/枚举校验，`candidate add --dry-run` 输出 endpoint、顶层字段、子表数量和脱敏联系字段摘要；真实写入不带 `--dry-run` 会被硬阻断。同步更新 `docs/research/2026-05-26-crm-candidate-add-api-contract.md`，明确当前实现状态和后续补证项。验证：新增测试红灯后实现，聚焦 `6 passed`；样例 payload validate/dry-run 通过；`py_compile`、`git diff --check`、敏感信息扫描和冲突标记扫描通过；全量 `python -m pytest tests scripts -q` -> `885 passed, 1 warning`，warning 为既有 `scripts/test_boss.py` event loop deprecation。
  - [x] Task 9：补登录态失效响应和只读重复候选人预检。已用无 Cookie 请求确认读接口返回 `{"status": false, "message": "login required"}`；前端脚本发现 `/rest/candidate/email_autocomplete?email=<email>&type=<type>` 可作为邮箱重复预检，不需要提交新增保存请求。CLI 新增 `auth check` 和 `candidate duplicate-check`，其中重复预检返回码 `0`=未命中、`2`=发现可能重复、`1`=请求/登录态错误，输出中查询邮箱脱敏。验证：聚焦 `10 passed`；live `auth check --no-cookie` 返回 `authenticated=false/message=login required`；全量 `python -m pytest tests scripts -q` -> `889 passed, 1 warning`；真实保存接口重复失败响应仍未用写请求探测。
  - [x] Task 10：实现 CRM 只读 lookup CLI。计划：先按 TDD 补 `lookup tree` 和 `lookup company` 测试；再封装城市/行业/职能/渠道/文件夹树查询与公司 autocomplete 查询；最后运行聚焦测试、全量测试、脱敏扫描和 diff 检查。边界：只读 GET、不保存 Cookie、不输出候选人隐私，不触发新增保存。已新增 `lookup tree --kind city|industry|function|channel|folder --query <text>` 和 `lookup company --name <text>`；树查询会扁平化返回 `id/label/path`，公司查询返回 `id/name/people_count/city`。验证：聚焦 `12 passed`；`py_compile`、敏感信息扫描、冲突标记扫描、`git diff --check` 通过；全量 `python -m pytest tests scripts -q` -> `891 passed, 1 warning`。
  - [x] Task 11：补 CRM `owner` 用户查询和工作经历部门查询。计划：先按 TDD 补 `lookup user` 与 `lookup department` 的红灯测试；再封装 `/rest/data/userlist` 和 `/rest/clientdepartment/listdepartment?client=<id>`；最后跑聚焦/全量测试、脱敏扫描和 diff 检查。边界：只读 GET，不输出用户邮箱明文，不写 CRM。已新增 `lookup user --query <name>` 和 `lookup department --client-id <id> --query <name>`；用户查询输出中邮箱统一为 `[REDACTED]`，部门查询返回扁平化 `id/label/path`。验证：聚焦 `14 passed`；`py_compile`、敏感信息扫描、冲突标记扫描、`git diff --check` 通过；全量 `python -m pytest tests scripts -q` -> `893 passed, 1 warning`。
  - [x] Task 12：实现 `candidate compose`，把人类可读草稿转换为 CRM payload JSON。计划：先按 TDD 补 compose 成功和缺失 lookup 的红灯测试；再实现本地 lookup cache 解析；最后验证 compose 产物可被 `candidate validate` 和 `candidate add --dry-run` 使用。边界：离线转换，不联网，不写 CRM，不保存 Cookie。Review：已新增离线 `candidate compose --input draft.json --lookup-cache lookup-cache.json --output candidate.json`，支持城市/行业/职能/渠道/文件夹/owner/公司/部门 label 到 ID 的本地映射，生成 `candidateexperience_set`、`candidateeducation_set` 和 `note_set` 后走现有 payload 校验；缺失 lookup 会返回 `error: lookup value not found for <kind>: <label>` 且不写输出文件。
  - Task 12 验证：`python -m pytest tests\test_crm_cli.py -q` -> `16 passed`；`python -m py_compile scripts\crm_cli.py` 通过；`python -m pytest tests scripts -q` -> `895 passed, 1 warning`，warning 为既有 `scripts/test_boss.py` event loop deprecation；敏感信息扫描、尾随空白/冲突标记扫描和 `git diff --check` 均通过。
  - [x] Task 13：增强 `candidate add --dry-run` 的请求合同摘要。计划：先按 TDD 补 headers/form/curl 模板和 `--output` 写文件测试；再实现脱敏请求摘要；最后验证仍不联网、不写 CRM、不泄露 Cookie 或候选人联系方式。边界：只生成请求结构和摘要，不生成真实写入确认参数。Review：`candidate add --dry-run` 现在输出脱敏 headers、form 结构、payload 字节数、sha256 和 PowerShell curl 模板；`--output request-summary.json` 可保存同一份摘要。摘要中的 Cookie 固定为 `[CRM_COOKIE]`，form data 固定为 `[REDACTED_PAYLOAD_JSON]`，测试夹具也改为 `placeholder.invalid` 和全零手机号以避免误报。验证：`python -m pytest tests\test_crm_cli.py -q` -> `17 passed`；`python -m py_compile scripts\crm_cli.py` 通过；`python -m pytest tests scripts -q` -> `896 passed, 1 warning`；敏感信息扫描、尾随空白/冲突标记扫描和 `git diff --check` 均通过。
  - [ ] Task 14：`candidateproject_set` 暂不实现，保留 TODO。后续只有在拿到包含项目经历的新增人才 live 抓包样本后，再按真实保存字段补 `candidate compose` 项目经历映射。边界：当前不新增 `_compose_project`，不新增项目经历测试，不把候选结构写入 API 合同。
  - [x] Task 15：从本地人才库抽一条样本做 CRM 新增 dry-run 探针。计划：只读 `data/talent.db`，选择一条有详情/经历/教育的样本；在系统临时目录生成脱敏/最小化 draft、lookup cache、payload 和 request-summary；执行 `candidate compose` 与 `candidate add --dry-run`，列出解析卡点。边界：不联网、不写 CRM、不把真实候选人隐私写入仓库或最终回复。Review：已从主库抽取 1 条有工作经历和教育经历的样本，生成临时探针目录 `%TEMP%\crm-dry-run-probe-20260526-132546`；样本只在最终摘要中保留候选人 ID 哈希。`candidate compose`、`candidate validate`、`candidate add --dry-run --output request-summary.json` 均返回 0；dry-run 摘要显示 `POST /rest/candidate/add?_v_user=300`、`candidateexperience_set=2`、`candidateeducation_set=1`、`candidateproject_set=0`、payload `1451` bytes。卡点：本次使用临时 synthetic lookup cache 补齐城市/公司/owner/channel/folder ID，下次真实写入前必须用 CRM lookup CLI 取真实 ID；本地城市可能是区县粒度，需要映射到 CRM city tree；本地库缺行业/职能/渠道/文件夹/owner 的业务默认规则；公司 autocomplete 与部门 ID 仍需真实查询；`candidateproject_set` 仍保持 TODO；保存接口不带 `_v` 是否接受仍需 live 验证。
  - Task 15 最终验证：`python -m pytest tests\test_crm_cli.py -q` -> `17 passed`；`python -m py_compile scripts\crm_cli.py`、`git diff --check` 和仓库敏感字符串扫描通过；`python -m pytest tests scripts -q` -> `896 passed, 1 warning`，warning 仍为既有 `scripts/test_boss.py` event loop deprecation。
  - [x] Task 16：固化 cold call 表单必填规则，并构建真实只读 lookup cache。计划：按用户补充把 cold call 必填限定为电话三选一、姓名、性别、所在城市、行业、职能、渠道、工作经历公司和职位；`owner/source/folders/education/note` 等不作为表单必填。先补回归测试，再改 `scripts/crm_cli.py` 校验和 compose 可选字段逻辑；随后用内置 Browser 登录态通过只读 GET/fetch 构建真实 lookup cache，替换 Task 15 synthetic cache 后再跑 compose/validate/add dry-run。边界：不提取或保存 Cookie，不执行 `/rest/candidate/add` 真实写入，`candidateproject_set` 继续保持 TODO。Review：已新增 cold call 必填回归并更新 `scripts/crm_cli.py`，当前 `validate` 强制电话三选一、姓名二选一、`gender/locations/industrys/functions/channel` 和工作经历公司/职位；`owner/source/folders` 不再作为表单必填，`compose` 允许省略 `owner/folders`，备注存在但无 owner 时不再强制生成 `noteuser_set`。真实 lookup cache 构建使用临时内存登录 session 和只读 GET，未保存 Cookie/密码，产物只落在 `%TEMP%\crm-dry-run-probe-20260526-132546`。第一轮真实 cache 命中城市 1、公司 2，但暴露本地样本缺行业/职能、城市区县粒度不匹配、channel/owner/folder 为 synthetic 名称；第二轮移除非必填 owner/folder，用真实 CRM 字典默认值补 city/industry/function/channel，并补测试用 gender 默认值后，`candidate compose`、`candidate validate`、`candidate add --dry-run --user-id 300` 全部返回 0。最终 dry-run 摘要：`POST /rest/candidate/add?_v_user=300`，`candidateexperience_set=2`、`candidateeducation_set=1`、`candidateproject_set=0`，payload `1424` bytes，sha256 `265a45c61db693125df69cf41ed8f3dd8d7d13e08411d54751ed54143f84b326`。剩余卡点：真实批量导入前必须为本地库补 `gender/industry/function/channel/currentLocation` 的确定性来源或人工选择规则；城市区县到 CRM city tree 的归一化仍需实现；真实写入仍未开放。
  - [x] Task 17：按用户确认固化 compose 默认规则。计划：`gender` 缺省为男，`industrys` 缺省按 label `AI` 查找，`functions` 缺省按 label `AI产品` 查找，`channel` 缺省按 label `脉脉-企业版付费账号` 查找；lookup 精确匹配优先，若仅有多个模糊匹配则取首个。边界：只改离线 compose 和只读 lookup 校验，不开放真实写入，`candidateproject_set` 继续保持 TODO。Review：已新增默认值和 lookup 匹配回归测试，`candidate compose` 现在会在 cold call 草稿缺少 `gender/industries/functions/channel` 时默认填男、AI、AI产品、脉脉渠道；lookup 精确优先，模糊多命中取首个。只读 live lookup 确认 `AI -> 188`、`AI产品 -> 1330`，渠道字典没有 `脉脉-企业版付费账号`，真实 label 为 `脉脉-企业付费账号 -> 400034`，CLI 已把它作为兼容默认别名。验证：红灯确认后实现；`python -m pytest tests\test_crm_cli.py -q` -> `23 passed`；`python -m py_compile scripts\crm_cli.py`、`git diff --check`、敏感字符串扫描通过；全量 `python -m pytest tests scripts -q` -> `902 passed, 1 warning`，warning 为既有 `scripts/test_boss.py` event loop deprecation。
  - [x] Task 18：用本地人才库样本执行混淆数据 CRM 新增真实写入并飞书通知。计划：先为 `candidate add` 增加显式真实写入保护参数和回归测试；再只读抽取 `data/talent.db` 一条有工作经历的人才，生成系统临时目录中的混淆 draft/payload；随后执行 `candidate add --dry-run`、重复预检、真实 `POST /rest/candidate/add`；最后把脱敏执行摘要发送飞书 IM。边界：不把 CRM 密码/Cookie/原始候选人隐私写入仓库或最终回复；只创建一条混淆测试人才；`candidateproject_set` 保持 TODO。Review：已新增 `--confirm-real-write` 显式确认参数，默认无 `--dry-run` 仍拒绝真实写入；真实写入摘要继续脱敏 Cookie/form.data/联系方式。已从本地人才库只读抽取 1 条有工作经历的样本，在系统临时目录 `%TEMP%\crm-live-add-test-20260526-150704` 生成混淆 draft、lookup cache、payload、dry-run 摘要、live 摘要和执行摘要。CLI 步骤 `compose/validate/add --dry-run/duplicate-check/add --confirm-real-write` 全部返回 0；dry-run payload `1221` bytes，sha256 `674d8e927809c39f1ffbf585258a239545560802be7c141e352f2c4b2c00d7e3`；真实保存返回 `status=true`、`candidate_id=1449522`、工作经历子记录 1 条、教育经历 0 条。lookup ID：city `102`、industry `188`、function `1330`、channel `400034`、company `46033`、owner `300`。飞书 IM 已用 user 身份发送到当前授权用户，`message_id=om_x100b6e60235d94c8b118dfff253ce1e`。lark-cli 提示当前 `1.0.36` 可更新到 `1.0.39`。验证：`python -m pytest tests\test_crm_cli.py -q` -> `24 passed`；`python -m py_compile scripts\crm_cli.py`、`git diff --check`、仓库和临时产物凭据/CRM Cookie/原始候选隐私扫描通过；全量 `python -m pytest tests scripts -q` -> `903 passed, 1 warning`，warning 为既有 `scripts/test_boss.py` event loop deprecation。
  - Review：已完成新增人才 API 反查。确认入口 `/crm#candidate/add`，保存接口 `POST /rest/candidate/add?_v=<request-version>&_v_user=300`，请求体为 `application/x-www-form-urlencoded`，关键参数 `data=<JSON string>`；必要头为 `X-Requested-With: XMLHttpRequest`、`x-request-id`、`Origin`、`Referer` 和运行时 Cookie，未观察到 CSRF/Authorization。payload 包含顶层人才字段、`candidateexperience_set`、`candidateeducation_set`、`note_set`，成功响应顶层 `data` 为 candidate id，子记录 id 在 `current_message.candidateexperience[]/candidateeducation[]`。详情页元数据接口 `GET /rest/custom_field/candidate/detail?...&suffix=coldcall` 已确认，可用于 CLI 字段 schema、枚举校验和 label/code 映射；主要查询接口已通过 CDP 登录态验证，覆盖城市/行业/职能树、公司、渠道、文件夹、用户和部门。已将本地 payload JSON 改为脱敏样例模板，原始 Cookie、账号密码、真实邮箱/手机号和真实内部 ID 未写入仓库。当前已实现最小 Python CLI：`metadata candidate`、`auth check`、`candidate validate`、`candidate duplicate-check`、`candidate add --dry-run`；真实写入前仍需补保存接口重复候选人/登录过期错误响应和 `candidateproject_set`。

- [x] JD 推荐反馈闭环阶段一实现（2026-05-26）：按 `docs/superpowers/plans/2026-05-26-jd-delivery-feedback-phase1.md` 实现反馈采集和编译第一阶段，保持 `data/talent.db` 只读、不上传猎头备注、不自动修改评分卡。
  - [x] Plan：按 5 个任务执行：反馈编译器合同、外联表反馈列、发布预检兼容、workflow/skill 文档、最终验证。
  - [x] Verify Plan：代码改动限定为计划列出的 scripts/schemas/tests/workflow/skill 文件；执行中每个任务遵守 TDD，先红灯再实现；验证使用 `.venv/bin/python`。
  - [x] Task 1：反馈编译器合同。
  - [x] Task 2：外联表反馈列。
  - [x] Task 3：发布预检兼容。
  - [x] Task 4：workflow/skill 文档。
  - [x] Task 5：最终验证。
  - Review：已完成阶段一实现。新增 `scripts/jd_delivery_feedback.py`、`schemas/jd-delivery-feedback.schema.json` 和 `tests/test_jd_delivery_feedback.py`，支持 `delivery-feedback.json` 校验、原因码校验、重复候选/排名校验、Top10/Top30 指标、分档认可率和 CLI 编译 `feedback-summary.json` / `calibration-suggestions.json`；CLI 校验失败返回 1 并输出 `error:`，不打 traceback。`reports/outreach-queue.csv` 现追加 8 个空反馈列：`feedback_label`、`feedback_stage`、`reason_codes`、`hunter_note`、`contacted`、`submitted_to_client`、`interviewed`、`offer`；发布预检测试确认空反馈列不会阻断飞书 Sheet 发布，`scripts/jd_talent_delivery_feishu.py` 无需修改。`agents/workflows/jd-talent-delivery/AGENT.md` 和 `skills/jd-talent-delivery/SKILL.md` 已新增 S9/猎头反馈后续合同，明确可选后续、默认 dry-run、不写 `data/talent.db`、不自动修改评分卡、不自动发布猎头备注。验证：聚焦测试 `81 passed`；编译、schema 校验、`git diff --check` 通过；全量 `.venv/bin/python -m pytest tests scripts -q` -> `879 passed, 1 warning`，warning 为既有 `scripts/test_boss.py` event loop deprecation。

- [x] JD 推荐反馈闭环阶段一实施计划（2026-05-26）：基于 `docs/design-discussions/2026-05-25-jd-delivery-feedback-optimization-design.md`，为反馈采集和编译阶段写可执行 TDD 实施计划。
  - [x] Plan：只新增实施计划文档，不改业务实现；计划覆盖反馈 schema/编译器、外联表反馈列、发布回读兼容和 workflow/skill 文档同步。
  - [x] Verify Plan：待修改文件限定为 `docs/superpowers/plans/2026-05-26-jd-delivery-feedback-phase1.md`、`tasks/todo.md`、`tasks/archive/2026-05.md`；验证方式为计划自检、占位符/冲突标记扫描、`git diff --check`。
  - [x] 梳理阶段一文件边界和任务拆分。
  - [x] 写入实施计划。
  - [x] 自检计划覆盖设计文档阶段一要求。
  - Review：实施计划已写入 `docs/superpowers/plans/2026-05-26-jd-delivery-feedback-phase1.md`，按 writing-plans 格式拆为 5 个任务：反馈编译器合同、外联表反馈列、发布预检兼容、workflow/skill 文档、最终验证。计划明确只做阶段一，不做历史回放、评分卡模板选择和 reranker。未修改业务代码。

- [x] JD 推荐闭环精准度优化设计（2026-05-25）：承接会话 `019e5f8c-5851-7ff1-bae6-3372b3ac5013` 中“同意，设计先行”，设计 JD 画像、评分卡、人选匹配和猎头反馈闭环的可标注、可回放、可校准方案。
  - [x] Plan：只写设计文档和任务记录，不修改业务代码；先基于当前 `jd-talent-delivery` workflow、画像/评分/匹配脚本和既有 feedback 脚本梳理边界。
  - [x] Verify Plan：待修改文件限定为 `docs/design-discussions/2026-05-25-jd-delivery-feedback-optimization-design.md`、`tasks/todo.md` 和归档；验证方式为格式检查、占位符/矛盾扫描、`git diff --check`。
  - [x] 梳理现有 JD delivery 产物链路和反馈脚本能力。
  - [x] 设计反馈 schema、离线回放指标、评分卡模板库和迭代策略。
  - [x] 写入设计文档并做自检。
  - Review：已写入 `docs/design-discussions/2026-05-25-jd-delivery-feedback-optimization-design.md`，方案采用“反馈优先 + 离线回放”的确定性闭环：外联表追加猎头反馈列，新增 JD delivery 反馈 JSON、原因码体系、反馈编译、历史 run 回放指标、评分卡模板库和后续轻量 reranker 触发条件。范围只到设计文档和任务记录，未修改业务代码。完整记录已归档到 `tasks/archive/2026-05.md`。

- [x] 查找项目下最近的对话记录（2026-05-25）：定位 `talent-agent` 相关且不在当前帐户下的最近对话/会话线索，只读检索项目文件、任务归档和本机 agent 会话索引，不修改业务代码。
  - [x] Plan：先查项目内 `.claude`/`.claudecode`、`tasks/`、`memory/`、`data/output/` 等可能记录对话或交付轨迹的位置，再按项目路径在本机 Codex/Claude 相关会话目录做定向检索。
  - [x] Verify Plan：边界为只读搜索和任务台账记录；待查看文件为项目工作台、归档、隐藏 agent 配置和本机会话索引；验证方式为文件时间排序、关键词检索、路径匹配和最近候选摘要比对。
  - [x] 检查项目内最近任务记录、归档和隐藏 agent 配置。
  - [x] 搜索本机当前/非当前帐户下与 `/Users/eric/workspace/talent-agent` 相关的最近会话索引。
  - [x] 汇总最近候选的路径、时间、来源帐户线索和可信度。
  - Review：项目内未发现真实对话正文，`.claude` 为 Claude adapter，`.claudecode` 只有工具参数提示；真实 Codex 会话在 `/Users/eric/.codex/sessions/`。当前对话为 `019e5fb3-3ed6-7ee0-badf-aaab8d384e6d`，`model_provider=openai`，开始 `2026-05-25 23:14:03 +0800`。按“非当前帐户/非当前 provider”理解，最近候选是 `/Users/eric/.codex/sessions/2026/05/25/rollout-2026-05-25T22-31-33-019e5f8c-5851-7ff1-bae6-3372b3ac5013.jsonl`，`model_provider=custom`，`cwd=/Users/eric/workspace/talent-agent`，mtime `2026-05-25 23:07:42 +0800`，主题为“制定人才推荐闭环优化方案”；最近用户消息包括“同意，设计先行”。其他相邻 custom 候选为 `22:55:22`、`22:49:17`、`21:25:07`。本轮未展开完整正文，只提取元数据与首末用户消息。

- [x] 调查 `.agents/skills` 本地代码来源与有效性（2026-05-25）：确认这些技能文件是否属于当前 GitHub 最新版本、何时产生、是否被仓库运行时引用，以及是否可以视为废弃/本地扩展。
  - [x] Plan：只调查 `.agents/skills` 及相关引用，不删除文件、不改业务逻辑；必要记录写入 `tasks/todo.md` 与归档。
  - [x] Verify Plan：修改边界为任务台账；调查文件包括 `.agents/skills/**`、仓库 workflow/skill 引用、git 远端与本地历史；验证方式为 `git fetch`、`git status/log/diff/ls-tree`、`rg` 引用搜索、JSON/Python 语法检查和仓库测试。
  - [x] 检查 `.agents/skills` 的文件清单、git 跟踪状态、创建/修改时间与最近提交归属。
  - [x] 对比 `origin/main`/GitHub 最新远端，确认远端是否包含 `.agents/skills`。
  - [x] 搜索仓库运行时、测试、AGENTS/workflow 对 `.agents/skills` 的引用，判断是否参与执行。
  - [x] 检查 `.agents/skills` 内是否包含可执行 Python/脚本、JSON 是否有效、是否与 canonical `skills/` 或 `agents/workflows/` 重复。
  - [x] 汇总结论、风险和建议，并运行必要验证。
  - Review：`.agents/skills` 不在 `HEAD/origin/main`，无 git 历史，当前为未跟踪本地目录；文件创建时间集中在 `2026-05-24 21:14-21:16 +0800`。内容是 `.claude/skills` 的 Codex 适配副本，规则/脚本落后于当前 canonical `rules/` 和 `scripts/`。结论：它不是 GitHub 最新版本的一部分，也不是业务代码权威来源；仅可视作本地 Codex skill 入口/残留 adapter。已按用户确认删除本地 `.agents/skills`，空 `.agents` 目录也已移除。完整记录已归档到 `tasks/archive/2026-05.md`；验证：`git diff --check` 通过，`.agents` JSON/Python 语法检查通过，`.venv/bin/python -m pytest tests scripts -q` -> `862 passed, 1 warning`。

- [x] 本机 Python 环境固定与跨平台路径测试修复（2026-05-25）：按方案 1+2 配置 Homebrew Python + 项目 `.venv`，并修复 `tests/test_maimai_campaign_orchestrator.py` 的 Windows/macOS 路径分隔符断言。
  - [x] 复现路径分隔符测试失败，确认本机 Python/PATH 当前状态。
  - [x] 安装或复用 Homebrew Python 3.12，创建 `.venv` 并安装依赖。
  - [x] 更新 `~/.zshrc`，让新终端里的 `python` 指向 Homebrew Python。
  - [x] 修复测试断言为跨平台路径归一化比较。
  - [x] 使用 `.venv/bin/python` 运行聚焦测试和全量测试。
  - [x] 写回 Review，并把完整记录归档。
  - Review：已用 bundled Python 复现 `tests/test_maimai_campaign_orchestrator.py` 中 2 个路径断言失败，根因为测试写死 Windows `\` 分隔符；现已改为按 argv 取参数并用 `_portable_path()` 归一化后比较。Homebrew `python@3.12` 已通过 USTC bottle mirror 安装为 `Python 3.12.13`；`/Users/eric/.zshrc` 已加入 Homebrew shellenv 和 `python@3.12` libexec PATH，新交互 zsh 中 `python/python3/pip` 均指向 Homebrew Python。项目 `.venv` 已用 Homebrew Python 创建并安装 `requirements.txt`，`.venv/` 已加入 `.gitignore`。验证：修复前 2 个聚焦用例 `2 failed`；修复后 `.venv/bin/python -m pytest tests/test_maimai_campaign_orchestrator.py -q` -> `31 passed`；仓库要求 `.venv/bin/python -m pytest tests scripts -q` -> `860 passed, 1 warning`，warning 为既有 `scripts/test_boss.py` event loop deprecation。完整记录已迁移到 `tasks/archive/2026-05.md`。

- [x] 读取飞书 Wiki 并做本地人才库推荐（2026-05-25，Y69DwM483iPeU2krcLvcvFgBnSf）：读取 `https://sq8org1v4k6.feishu.cn/wiki/Y69DwM483iPeU2krcLvcvFgBnSf?fromScene=spaceOverview`，过滤非 JD 信息后整理为标准 JD，再基于只读 `data/talent.db` 生成 Top30 推荐、发布飞书并通知。
  - [x] S0 前置检查：workflow、`data/talent.db` 只读可用、`lark-cli` 鉴权与必要 scope。
  - [x] S1 读取 Wiki/Doc 正文，抽取岗位职责、任职要求、候选人画像，过滤页面导航、协作说明、流程噪声和无关信息。
  - [x] S2 标准 JD 落盘到 `docs/business-requirements/`，保留来源引用和招聘参考信息。
  - [x] S3-S6 生成岗位画像、评分卡、粗筛、精排、推荐报告和外联表，必要时回到评分卡收敛后重跑。
  - [x] S7-S8 发布到飞书 Wiki，回读 Wiki/Doc/Sheet，并发送 `JD需求协同` 完成通知。
  - [x] 记录 Review：交付链接、Top30 分层、质量门、验证命令和风险边界。
  - Review：已读取 Wiki 节点 `Y69DwM483iPeU2krcLvcvFgBnSf`，解析为 docx `M5fHdOP9foHGRhxNkYJcgG1Onoc`，标题“腾讯游戏-多模态策略产品经理/专家(深圳)”。标准 JD 已落盘 `docs/business-requirements/12-tencent-games-multimodal-strategy-product-manager.md`，把多模态策略产品、AI 产品、视频生成、模型评测、数据策略、指标体系、数据分析、产品规划和项目推动作为评分输入，把薪资、职级、面试流程、HC、WP 提交说明列为招聘参考；“训练/推理/数据工程都可以看”与本岗位产品经理方向不一致，未作为本岗位硬门槛。输出目录：`data/output/12-tencent-games-multimodal-strategy-product-manager-2026-05-25`。自动画像首版误把数据工程纳入 must-have 且缺少评测/产品信号，已回到 S2/S3 手工收敛为 `v2-product-evaluation-balanced`：`must_have=12/nice_to_have=20`；最终粗筛 `19881` 人、精排 `343` 人，Top30 `A=1/B=29/C=0/淘汰=0`，`reports/quality-gates.json status=passed` 且无 warnings。飞书已真实发布并回读：Wiki 目录 `https://sq8org1v4k6.feishu.cn/wiki/VsdxwMhwBiWh2okIeDAcKdYpnNg`，JD `https://sq8org1v4k6.feishu.cn/docx/WTQUdmLASoFjyOxiUf0c9km3nIb`，岗位画像 `https://sq8org1v4k6.feishu.cn/docx/KXVOdSunDowiJLxSIy2cGDRcnxh`，推荐报告 `https://sq8org1v4k6.feishu.cn/docx/PdYhdnLiNoAep9xXByTcl48jnXe`，外联表 `https://sq8org1v4k6.feishu.cn/sheets/BzBVsCyi8hE1s8tMlW6ciYBdnPE`。回读证据：Wiki 子节点 4 个、3 个 Doc outline 成功、Sheet preview 1 个，外联表 30 行；完成通知已发到 `JD需求协同`，`message_id=om_x100b6e765583bca0b14723b9b442afd`。主库只读验证：`candidates=19881/source_profiles=19881/candidate_details=19881/match_scores=0`，`PRAGMA integrity_check=ok`，未触发平台搜索。验证：`python -m pytest tests\test_jd_talent_delivery_profile.py tests\test_jd_talent_delivery_scorecard.py tests\test_jd_talent_delivery_match.py tests\test_jd_talent_delivery_feishu.py -q` -> `59 passed`；`python -m py_compile scripts\jd_talent_delivery_profile.py scripts\jd_talent_delivery_scorecard.py scripts\jd_talent_delivery_match.py scripts\jd_talent_delivery_feishu.py` 通过；`git diff --check` 通过；交付源/画像/评分/报告/通知/发布清单敏感与乱码标记扫描无命中；`lark-cli doctor` ok 但提示当前 `1.0.36` 可更新到 `1.0.39`。

- [x] 读取飞书 Wiki 并做本地人才库推荐（2026-05-25，IXkZw7rVkiYJerktN7RcwLkIntc）：读取 `https://sq8org1v4k6.feishu.cn/wiki/IXkZw7rVkiYJerktN7RcwLkIntc?fromScene=spaceOverview`，过滤非 JD 信息后整理为标准 JD，再基于只读 `data/talent.db` 生成 Top30 推荐、发布飞书并通知。
  - [x] 前置检查：仓库 workflow、`data/talent.db` 只读可用、`lark-cli` 鉴权和 scope。
  - [x] 解析 Wiki 节点与正文，抽取与岗位 JD 相关的信息，过滤页面导航、协作说明、流程噪音和无关信息。
  - [x] 将清洗后的标准 JD 落盘到 `docs/business-requirements/`，并保留来源引用。
  - [x] 执行 `jd-talent-delivery`：生成岗位画像、评分卡、粗筛、精排、推荐报告和外联表。
  - [x] 跑质量门、飞书发布/回读和完成通知，记录产物链接与验证结果。
  - [x] 更新 Review，说明推荐口径、Top30 分层、验证命令和风险边界。
  - Review：已读取 Wiki 节点 `IXkZw7rVkiYJerktN7RcwLkIntc`，解析为 docx `GX6SddFF4o9ILdxV7PKcChiWnfb`，标题“腾讯游戏训练推理数据工程研发专家/工程师”。标准 JD 已落盘 `docs/business-requirements/11-tencent-games-training-inference-data-engineering.md`，把训练/推理/数据工程职责和 GPU/CUDA、FSDP/DeepSpeed/Megatron、vLLM/SGLang、KV Cache、OpenRLHF/RLHF 等硬要求作为评分输入，把 HC、薪资、面试流程、WP 协作说明列为招聘参考。输出目录：`data/output/11-tencent-games-training-inference-data-engineering-2026-05-25`。初版评分卡因硬词过细导致精排为 0，已回到 S3 收敛为 `v3-recall-balanced`：`must_have=12/nice_to_have=29`，粗筛用于召回、精排用于证据排序；最终粗筛 `19881` 人、精排 `311` 人，Top30 `A=0/B=4/C=26/淘汰=0`，`reports/quality-gates.json status=passed` 且无 warnings。该岗位结果偏召回，Top30 中 C 类较多，不能包装成高置信强推荐；后续若要更高精度，应继续收紧精排规则，要求命中训练系统/分布式训练或推理系统/性能优化之一。飞书已真实发布并回读：Wiki 目录 `https://sq8org1v4k6.feishu.cn/wiki/XlEpw0BOjiNozvkWP3bc2S1VnlV`，JD `https://sq8org1v4k6.feishu.cn/docx/Xp5lduXgbob9lOxMwcLcU3OknSH`，岗位画像 `https://sq8org1v4k6.feishu.cn/docx/D8D3dg9BHouMIvx8Zc2cKYRpnVf`，推荐报告 `https://sq8org1v4k6.feishu.cn/docx/DG7vduTNIozwghxM1R2ca6OjnuZ`，外联表 `https://sq8org1v4k6.feishu.cn/sheets/C6zhsLp48hhcDkte163cGeMBnph`。回读证据：Wiki 子节点 4 个、3 个 Doc outline 成功、Sheet preview 1 个，外联表 30 行；完成通知已发到 `JD需求协同`，`message_id=om_x100b6e754a5b8c80b250ceb04518507`。主库只读验证：`candidates=19881/source_profiles=19881/candidate_details=19881/match_scores=0`，`PRAGMA integrity_check=ok`，未触发平台搜索。验证：`python -m pytest tests\test_jd_talent_delivery_profile.py tests\test_jd_talent_delivery_scorecard.py tests\test_jd_talent_delivery_match.py tests\test_jd_talent_delivery_feishu.py -q` -> `59 passed`；`python -m py_compile scripts\jd_talent_delivery_profile.py scripts\jd_talent_delivery_scorecard.py scripts\jd_talent_delivery_match.py scripts\jd_talent_delivery_feishu.py` 通过；`git diff --check` 通过；交付源/画像/评分/报告敏感与乱码标记扫描无命中；`lark-cli doctor` ok 但提示当前 `1.0.36` 可更新到 `1.0.39`。

- [x] 读取飞书 Wiki 并做本地人才库推荐（2026-05-25）：读取 `https://sq8org1v4k6.feishu.cn/wiki/KiwdwyM0uiaA8jkafXHcVBJgn8e?fromScene=spaceOverview`，过滤非 JD 信息后整理为标准 JD，再基于只读 `data/talent.db` 生成 Top30 推荐与质量验证。
  - [x] 完成前置检查：仓库 workflow、`data/talent.db` 只读可用、`lark-cli` 鉴权和 scope。
  - [x] 拉取 Wiki 正文，抽取与岗位 JD 相关的信息，过滤流程噪音、页面导航和无关协作信息。
  - [x] 将清洗后的 JD 落盘到 `docs/business-requirements/`，并保留来源引用。
  - [x] 执行 `jd-talent-delivery`：生成岗位画像、评分卡、粗筛、精排、推荐报告和外联表。
  - [x] 跑质量门、飞书发布/回读和完成通知，记录产物链接与验证结果。
  - [x] 更新 Review，说明推荐口径、Top30 分层、验证命令和风险边界。
  - Review：已读取 Wiki 节点 `KiwdwyM0uiaA8jkafXHcVBJgn8e`，解析为 docx `SUhJdYCpioPzxfx83z7cBTDInfe`，无子节点；整理后的标准 JD 已落盘 `docs/business-requirements/10-tencent-games-multimodal-algorithm-researcher.md`，把岗位职责/要求/候选人画像作为评分输入，把薪资、面试流程、WP 协作说明列为招聘参考。输出目录：`data/output/10-tencent-games-multimodal-algorithm-researcher-2026-05-25`。主库只读验证：`candidates=19881/source_profiles=19881/candidate_details=19881`，`PRAGMA integrity_check=ok`，未写 `match_scores`，未触发平台搜索。初版评分卡因 26 个 must-have 过宽导致质量门 `blocked`，已参考历史多模态算法交付口径收敛为 v2 refined 评分卡并从 S4-S6 全量重跑；最终粗筛 `19881` 人、精排 `1461` 人，Top30 `A=1/B=29/C=0/淘汰=0`，`reports/quality-gates.json status=passed`。飞书已真实发布并回读：Wiki 目录 `https://sq8org1v4k6.feishu.cn/wiki/FWISwW75Ki2o8NkrMeqcttixnGb`，JD `https://sq8org1v4k6.feishu.cn/docx/Btecd85pOo71uEx1ZARcT38tnPb`，岗位画像 `https://sq8org1v4k6.feishu.cn/docx/NTqudSdJZogGqAxyClDc9wjxnpf`，推荐报告 `https://sq8org1v4k6.feishu.cn/docx/Kos2dUvrXoaoZLxaToycnhTlnUQ`，外联表 `https://sq8org1v4k6.feishu.cn/sheets/TWSDstJCMhagp6tlpfycsFlInSi`。回读证据：Wiki 子节点 4 个、3 个 Doc outline 成功、Sheet `A1:Z5` 与本地 CSV 前缀比对通过；完成通知已发到 `JD需求协同`，`message_id=om_x100b6e744bdfdc90b1157726fa44821`。验证：`python -m pytest tests\test_jd_talent_delivery_profile.py tests\test_jd_talent_delivery_scorecard.py tests\test_jd_talent_delivery_match.py -q` -> `20 passed`；敏感/乱码标记扫描无命中；`lark-cli doctor` ok 但提示当前 `1.0.36` 可更新到 `1.0.39`。

- [x] 导出人才库跨 PC 同步文件（2026-05-25）：从当前主库 `data/talent.db` 导出完整 `talent_sync` bundle，用于另一台 PC 导入同步；导出后执行 bundle 校验并记录文件大小、哈希和导入命令。
  - [x] 确认主库同步状态：`candidates=19881/sync_imports=11`。
  - [x] 导出完整 sync bundle 到 `data/output/`。
  - [x] 执行 `verify-bundle` 并计算 SHA256。
  - [x] 写回 Review，给出另一台 PC 的导入命令。
  - Review：已导出 `data/output/talent-sync-to-pc-2026-05-25/talent-sync-full-20260525-145358.zip`，大小 `71113203` bytes，SHA256 `ccc23e82cc6907d942480baf4beeca6a78a76b88f7e8fb5cf3193d6bd2155e5c`，`verify.ok=true`。bundle manifest：`export_id=93df45bf-f19e-478d-ae23-934b939a3750`，`source_node_id=f10862a8-f87f-498e-83c6-fd168448da08`，包含 `candidates=19881/source_profiles=19881/candidate_details=19881`。校验摘要：`data/output/talent-sync-to-pc-2026-05-25/talent-sync-full-verify-summary.json`。另一台 PC 先 dry-run：`python -m scripts.talent_sync import --db data\talent.db --bundle talent-sync-full-20260525-145358.zip`；确认后 apply：`python -m scripts.talent_sync import --db data\talent.db --bundle talent-sync-full-20260525-145358.zip --apply --confirm "确认同步人才库"`。

- [x] Tencent Campaign DB 同步到主库（2026-05-25）：按用户更正，只将 `data/campaigns/tencent-games-ai-100hc-broad-recall-2026-05-24/talent.db` 通过 `talent_sync` bundle 路径导入 `data/talent.db`，不处理其他 campaign 目录；先 dry-run、备份，再 apply，并保留冲突报告。
  - [x] 停止已中断的全 campaigns dry-run 残留进程，确认该阶段未写主库。
  - [x] 盘点 Tencent campaign `talent.db`、主库基线计数和已存在同步状态。
  - [x] 导出 Tencent sync bundle 并执行 `verify-bundle`。
  - [x] 对主库执行 import dry-run，记录 created/merged/conflicts/skipped。
  - [x] 备份主库后执行 `--apply --confirm "确认同步人才库"`。
  - [x] 核验主库计数、`PRAGMA integrity_check`、`pending_merges`/`sync_conflicts`，运行聚焦测试并写回 Review。
  - Review：只同步 `data/campaigns/tencent-games-ai-100hc-broad-recall-2026-05-24/talent.db`。导出 bundle：`data/output/tencent-games-main-sync-2026-05-25/tencent-games-ai-100hc-broad-recall-2026-05-24.zip`，`verify_ok=true`；主库备份：`data/backups/talent-before-tencent-games-sync-20260525-133243.db`，备份 `PRAGMA integrity_check=ok`。dry-run 候选人级计划为 `created=6549/merged=1704/conflicts=0/skipped=0`；apply 结果为候选人 `created=6549/merged=1704/conflicts=48/skipped=0`，详情 `created=6549/merged=1704/conflicts=1178/skipped=0`。主库从 `candidates=13332/source_profiles=13332/candidate_details=13332/sync_imports=10/sync_conflicts=1814` 增至 `candidates=19881/source_profiles=19881/candidate_details=19881/sync_imports=11/sync_conflicts=3040`，`pending_merges=0`，`PRAGMA integrity_check=ok`。最新冲突主要为 `candidate_detail.raw_data.maimai_list=908`、`candidate_detail.raw_data.maimai_detail_capture=270`；聚焦测试 `python -m pytest tests\test_talent_sync.py -q` -> `37 passed`。

- [x] 腾讯游戏 AI 岗位 P0-P2 缺失详情补抓（2026-05-25）：基于 `reports/missing-detail-p0-p2-2026-05-25.csv` 为未含 `maimai_detail_capture` 的 P0/P1/P2 人选生成补抓详情任务，4 并行无人值守抓取，只写 Campaign DB，不写主库。
  - [x] 生成独立补抓 pack 和 pack-index，不覆盖 2026-05-24 已完成的 11 个详情 pack。
  - [x] 预检 CDP 页面和详情抓取入口，确认登录/验证码/安全页无阻断。
  - [x] 以 4 个并行 worker 执行详情抓取；遇登录、验证码、403/429/432、非 JSON、模板漂移等阻断立即停机。
  - [x] 对抓取结果做 dry-run；clean 后 apply 到 Campaign DB `talent.db`。
  - [x] 复核 P0/P1/P2 缺失详情数量、Campaign DB integrity、主库未写边界，写回 Review。
  - Review：已生成 `12` 个独立补抓 pack：`detail-missing-p0-p2-pack-001..012`，目标 `1159` 人，4 并行无人值守抓取完成全部 `1159` 个 live detail job。`pack-006` 抓取 `100/100` 成功但 dry-run 发现 `2` 个候选人无工作经历，触发 `missing_work_experience` apply blocker；已保留原始 capture，生成 `detail-missing-p0-p2-pack-006-clean-98` 派生 capture，排除 `candidate_id=5671/5672` 后 dry-run clean。写入前已备份 Campaign DB：`backups/talent-before-missing-detail-apply-20260525-112017.db`。最终 apply 写入 Campaign DB `1157` 人，`failed_jobs=0/unmatched=0/apply_blockers=0`；`maimai_detail_capture` 覆盖从 `1004` 增至 `2161`。P0-P2 剩余未详情 `2` 人，均为 `detail_p1`：`5671 喻鹿鸣`、`5672 李鑫路`，原因均为 `missing_work_experience`。Campaign DB `PRAGMA integrity_check=ok`，`pending_merges=0/sync_conflicts=0`；主库 `data/talent.db` 未写，mtime 仍为 `2026/5/23 9:46:38`。收尾报告：`reports/missing-detail-p0-p2-capture-summary-2026-05-25.json/.md`、`reports/missing-detail-p0-p2-post-apply-2026-05-25.json`。

- [x] 提交并推送本次工作树更新（2026-05-25）：按用户要求把当前非忽略变更提交并推送到 `origin/main`，提交前核对敏感/生成物边界、运行测试和 diff hygiene。
  - [x] 审查当前分支、变更文件、未跟踪文件和忽略文件，确认 `data/talent.db`、DB WAL/SHM、zip 等本地产物不进入提交。
  - [x] 检查代码/文档 diff 范围，确认本次提交覆盖标准 JD、JD 画像增强、回归测试、任务账本和经验记录。
  - [x] 运行 `git diff --check`、关键脚本 `py_compile` 和仓库测试。
  - [x] 暂存后运行 `git diff --cached --check`。
  - [x] 提交本次非忽略更新并推送到 `origin/main`。
  - [x] 验证远端 HEAD、最终 `git status`，写回 Review。
  - Review：提交范围已核对为 8 个非忽略文件：3 个腾讯游戏 JD 标准稿、`scripts/jd_talent_delivery_profile.py` 多模态/训练推理画像提取增强、对应回归测试、`tasks/todo.md`、`tasks/lessons.md` 与 `memory/error-log.md`。`data/talent.db`、DB WAL/SHM、zip、`data/output` 飞书交付产物均未纳入提交。验证：`git diff --check` 通过；`git diff --cached --check` 通过；`python -m py_compile scripts\jd_talent_delivery_profile.py scripts\jd_talent_delivery_scorecard.py scripts\jd_talent_delivery_match.py scripts\jd_talent_delivery_feishu.py` 通过；`python -m pytest tests scripts -q` -> `862 passed, 1 warning`，warning 为既有 `scripts/test_boss.py` event loop deprecation；主库只读校验 `candidates=19881/source_profiles=19881/candidate_details=19881/match_scores=0`，`PRAGMA integrity_check=ok`。主提交 `e38bba0 Add Tencent Games JD delivery updates` 已推送到 `origin/main`；推送后 `git status --short --branch` 为 clean，`git rev-list --left-right --count HEAD...origin/main` 为 `0 0`，远端 `refs/heads/main` 指向 `e38bba04dbfbb6382454ffe6062ecec20b6bde4a`。

- [x] 腾讯游戏 AI 岗位 broad recall follow-up 续跑（换号后解除 500 日护栏，2026-05-24）：从 `state/search-wave-followup-003-resume-after-http-432-plan.json` 的恢复点继续，只写 Campaign DB，不写主库。
  - [x] 更新运行策略，明确本轮不再用旧账号 `500` 页上限截断 follow-up wave。
  - [x] 基于 after-http-432 恢复点生成 50 页 chunk 的续跑计划，不覆盖历史中断计划和 raw。
  - [x] 预检 CDP 人才银行页、登录/验证码状态和 `/api/ent/v3/search/basic` 模板。
  - [x] 执行 follow-up live gate；遇登录、验证码、429/403/432、非 JSON、模板漂移等平台阻断立即停机。
  - [x] 标准化成功页；若 run 完整/按 max_live_pages 正常停止，再做 Campaign DB clean dry-run/apply。
  - [x] 验证 Campaign DB 完整性、详情优先级和未写主库边界，写回 Review。
  - Blocked：换号后已把 `run-policy.json` 的搜索日护栏从 `500` 提到 `5000`，并生成独立续跑计划，不覆盖历史 432 中断计划。`search-wave-followup-004-after-account-switch` 和 `search-wave-followup-005-after-account-switch` 均正常跑满 `50` 页 chunk，并经 clean dry-run 自动 apply 到 Campaign DB：004 `raw=556/created=352/merged=204/pending=0/errors=0`，005 `raw=584/created=318/merged=266/pending=0/errors=0`；004 中 1 条无姓名联系人已在 contacts 聚合层记录为 `skipped_missing_name=1` 并跳过，canonical raw 保留不改。随后 `search-wave-followup-006-after-account-switch` 在 `unit-000068 page 6` 触发 `captcha_api`/HTTP 429，按规则硬停；已标准化成功 `49` 页作为 checkpoint，失败页未写 raw，该 partial wave 未导入 Campaign DB。当前 canonical raw/page-quality 为 `643` 页；Campaign DB 为 `candidates=6143/source_profiles=6143/candidate_details=6143/pending_merges=0/sync_conflicts=0`，`PRAGMA integrity_check=ok`；详情优先级已刷新为 `total_candidates=6143/detail_p0=32/detail_p1=1495/detail_p2=145/skip=4471`，详情抓取覆盖仍为 `maimai_detail_capture=1004`；未写主库 `data/talent.db`。中断证据：`reports/interruption-search-wave-followup-006-after-account-switch-captcha-api-2026-05-24.json`；恢复计划：`state/search-wave-followup-006-resume-after-captcha-plan.json`。恢复条件：人工处理验证码/安全提示后，回到人才银行页并手动执行一次搜索刷新 `/api/ent/v3/search/basic` 模板，再从该 resume plan 继续。验证：`python -m pytest tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_search_live_standardize.py -q` -> `42 passed`；`python -m py_compile scripts/maimai_ai_infra_pipeline.py scripts/maimai_search_live_standardize.py scripts/maimai_ai_infra_search_live_gate.py scripts/maimai_broad_recall_adaptive.py` 通过；`git diff --check` 通过。
  - Blocked 更新：用户处理验证码后，`search-wave-followup-006-resume-after-captcha` 与 `search-wave-followup-007-after-account-switch` 已分别跑满 50 页 chunk，并经 clean dry-run/apply 写入 Campaign DB；随后 `search-wave-followup-008-after-account-switch` 成功标准化 `49` 页，在 `unit-000108 page 6` 再次触发 `captcha_api`/HTTP 429，按平台阻断规则硬停，失败页未写 raw，该 partial wave 未导入 Campaign DB。当前 canonical raw/page-quality 为 `792` 页；Campaign DB 保持上一完整 apply 后的 `candidates=7606/source_profiles=7606/candidate_details=7606/pending_merges=0/sync_conflicts=0`，`PRAGMA integrity_check=ok`；详情抓取覆盖仍为 `maimai_detail_capture=1004`；未写主库 `data/talent.db`。中断证据：`reports/interruption-search-wave-followup-008-after-account-switch-captcha-api-2026-05-24.json`；恢复计划：`state/search-wave-followup-008-resume-after-captcha-plan.json`，首个恢复 batch 为 `unit-000108 start_page=6`。阻断后剩余可继续 unit `29` 个，理论剩余页 `374`，运行策略日护栏仍为 `5000`。恢复条件：人工处理验证码/安全提示后，回到人才银行页并手动执行一次搜索刷新 `/api/ent/v3/search/basic` 模板，再从该 resume plan 继续。
  - 操作要求：用户要求“再次中断后关闭计算机”。下次从 `search-wave-followup-008-resume-after-captcha-plan.json` 继续无人值守时，如果再次遇到登录、验证码、403/429/432、非 JSON、模板漂移等平台阻断，必须先完成 checkpoint 标准化、中断报告、continuation/resume plan、DB/主库边界核验和任务台账更新，再执行 Windows 关机。
  - Blocked 更新三：用户再次处理验证码后已继续执行。`search-wave-followup-008-resume-after-captcha` 正常跑满 50 页并 clean apply 到 Campaign DB：`raw=712/created=363/merged=349/pending=0/errors=0`；`search-wave-followup-009-after-account-switch` 正常跑满 50 页并 clean apply：`raw=589/created=194/merged=395/pending=0/errors=0`。随后 `search-wave-followup-010-after-account-switch` 在 `unit-000131 page 5` 触发 `captcha_api`/HTTP 429，已按规则硬停；成功 `48` 页已标准化为 checkpoint，失败页未写 raw，该 partial wave 未导入 Campaign DB。当前 canonical raw/page-quality 为 `940` 页；Campaign DB 保持上一完整 apply 后的 `candidates=8163/source_profiles=8163/candidate_details=8163/pending_merges=0/sync_conflicts=0`，`PRAGMA integrity_check=ok`；详情抓取覆盖仍为 `maimai_detail_capture=1004`；未写主库 `data/talent.db`。中断证据：`reports/interruption-search-wave-followup-010-after-account-switch-captcha-api-2026-05-25.json`；恢复计划：`state/search-wave-followup-010-resume-after-captcha-plan.json`，首个恢复 batch 为 `unit-000131 start_page=5`；阻断后剩余可继续 unit `6` 个，理论剩余页 `76`。按用户要求，完成本次收尾后执行 Windows 关机。
  - Review：用户随后要求取消自动关机并继续执行，已确认无 `Stop-Computer`/`shutdown.exe` 残留进程；重新打开测试浏览器并等待用户登录/搜索后，从 `state/search-wave-followup-010-resume-after-captcha-plan.json` 继续。`search-wave-followup-010-resume-after-captcha` 已完成所有剩余可执行页，live run `status=completed/stopReason=null`，标准化 `38` 页，clean dry-run/apply 到 Campaign DB：`raw=436/created=90/merged=346/pending=0/errors=0`。最终 canonical raw/page-quality 为 `978` 页；adaptive state 为 `exhausted=1/stopped_low_quality=135`，`eligible_units=0/remaining_potential_pages=0`；Campaign DB 为 `candidates=8253/source_profiles=8253/candidate_details=8253/pending_merges=0/sync_conflicts=0`，`PRAGMA integrity_check=ok`；详情优先级已刷新为 `detail_p0=32/detail_p1=1951/detail_p2=180/skip=6090`，详情抓取覆盖仍为 `maimai_detail_capture=1004`；未写主库 `data/talent.db`。最终状态：`state/continuation-plan.json` 已改为 `completed_followup_search`，收尾报告 `reports/followup-closeout-2026-05-25.json`，宽召回摘要 `reports/broad-recall-summary.json/.md`。

- [ ] 腾讯游戏 AI 岗位 broad recall follow-up wave（2026-05-24）：基于既有 `page-quality/adaptive state` 从可继续 unit 的 page 3 开始补跑后续召回，仍只写 Campaign DB，不写主库。
  - [x] 只读核对 campaign root、run-policy、raw 页分布和 adaptive state。
  - [x] 生成 50 页以内 follow-up wave 计划，并校验不包含低质停止 unit、不覆盖既有 page 1/2 raw。
  - [x] 预检 CDP 人才银行页、登录/验证码状态和 `/api/ent/v3/search/basic` 搜索模板。
  - [x] 执行 follow-up wave；遇登录、验证码、429/403/432、非 JSON、模板漂移等平台阻断立即停机。
  - [x] 标准化 follow-up checkpoint raw；因 wave 被验证码/API 阻断，不做 Campaign DB import/apply、详情或摘要更新。
  - [x] 写回 Review，明确新增页数、候选人变化、验证结果和未写主库边界。
  - Blocked：`search-wave-followup-001` 已执行到 `unit-000005 page 7` 触发 `captcha_api`/HTTP 429，live gate 按规则硬停机，未继续请求。run 文件：`raw/search-live-runs/search-wave-followup-001-run.json`；中断证据：`reports/interruption-search-wave-followup-001-captcha-api-2026-05-24.json`；恢复计划：`state/search-wave-followup-001-resume-after-captcha-plan.json`。本轮成功标准化 `25` 个 follow-up 搜索页，canonical raw 从 `272` 页增到 `297` 页，`reports/page-quality.jsonl` 从 `272` 行增到 `297` 行；失败页未写 raw。执行中 `unit-000001`、`unit-000002`、`unit-000003`、`unit-000004` 已根据新页质动态继续并最终判为低质，`unit-000005` 已完成 page 3-6，page 7 被验证码/API 阻断；阻断后仍有 `123` 个 unit 可后续继续。Campaign DB 未导入本轮 partial follow-up，仍为 `candidates=3783/source_profiles=3783/candidate_details=3783/pending_merges=0/sync_conflicts=0`，`PRAGMA integrity_check=ok`；未写主库 `data/talent.db`。恢复条件：人工处理验证码/安全提示，回到人才银行页并手动执行一次搜索刷新 `/api/ent/v3/search/basic` 模板后，用 resume plan 继续。
  - Blocked 更新：用户处理验证码后，已继续执行 `search-wave-followup-001-resume-after-captcha` 和 `search-wave-followup-002`，两段均以 `completed_limited/max_live_pages` 在 50 页护栏处正常停止，已标准化并经 clean dry-run 自动 apply 到 Campaign DB。随后继续 `search-wave-followup-003`，在 `unit-000035 page 5` 再次触发 `captcha_api`/HTTP 429，已硬停并只标准化 checkpoint raw，不导入该 partial 段。新增产物：`raw/search-live-runs/search-wave-followup-001-resume-after-captcha-run.json`、`raw/search-live-runs/search-wave-followup-002-run.json`、`raw/search-live-runs/search-wave-followup-003-run.json`、`reports/interruption-search-wave-followup-003-captcha-api-2026-05-24.json`、`state/search-wave-followup-003-resume-after-captcha-plan.json`。截至本次停机，canonical raw/page-quality 为 `446` 页，500 页护栏剩余 `54` 页；Campaign DB 已从 `3783` 增至 `5473` 人，`source_profiles=5473/candidate_details=5473/pending_merges=0/sync_conflicts=0`，`PRAGMA integrity_check=ok`；详情抓取覆盖仍为 `maimai_detail_capture=1004`，未启动新详情抓取，未写主库 `data/talent.db`。当前详情优先级已刷新到 `total_candidates=5473`，`detail_p0=32/detail_p1=1373/detail_p2=111/skip=3957`。验证：`python -m pytest tests\test_maimai_ai_infra_search_live_gate.py::test_run_gate_adaptive_max_live_pages_preserves_next_page_state tests\test_maimai_ai_infra_search_live_gate.py::test_run_gate_adaptive_quality_continues_good_unit_to_page_three tests\test_maimai_search_live_standardize.py::test_standardize_live_run_writes_successful_pages_to_canonical_raw -q` -> `3 passed`；`git diff --check` 通过。恢复条件同上：人工处理验证码/安全提示后，回到人才银行页并手动执行一次搜索刷新模板，再从 `state/search-wave-followup-003-resume-after-captcha-plan.json` 继续。
  - Blocked 更新二：用户再次处理验证码后，已从 `state/search-wave-followup-003-resume-after-captcha-plan.json` 继续执行。`search-wave-followup-003-resume-after-captcha` 成功标准化 `48` 页后，在 `unit-000042 page 4` 触发 `http_432`，已按平台风控规则硬停机；失败页未写 raw，partial wave 未导入 Campaign DB。新增产物：`raw/search-live-runs/search-wave-followup-003-resume-after-captcha-run.json`、`reports/interruption-search-wave-followup-003-resume-after-captcha-http-432-2026-05-24.json`、`state/search-wave-followup-003-resume-after-http-432-plan.json`。截至本次停机，canonical raw/page-quality 为 `494` 页，500 页护栏仅剩 `6` 页；Campaign DB 保持 `candidates=5473/source_profiles=5473/candidate_details=5473/pending_merges=0/sync_conflicts=0`，`PRAGMA integrity_check=ok`；详情抓取覆盖仍为 `maimai_detail_capture=1004`，未启动新详情抓取，未写主库 `data/talent.db`。详情优先级保持 `total_candidates=5473`、`detail_p0=32/detail_p1=1373/detail_p2=111/skip=3957`。验证：`python -m pytest tests\test_maimai_ai_infra_search_live_gate.py::test_run_gate_adaptive_max_live_pages_preserves_next_page_state tests\test_maimai_search_live_standardize.py::test_standardize_live_run_writes_successful_pages_to_canonical_raw -q` -> `2 passed`；`git diff --check` 通过。恢复条件：人工处理 HTTP 432/安全提示后，回到人才银行页并手动执行一次搜索刷新模板，再从 `state/search-wave-followup-003-resume-after-http-432-plan.json` 继续；但因今日搜索页护栏只剩 `6` 页，建议后续只补完剩余预算或转入详情优先级复核。

- [x] 补齐 `broad_recall_adaptive_v1` 在线自适应扩页设计并实施（2026-05-24）。
  - [x] 补充设计：明确 live gate 按页评分、状态持久化、跳组规则和旧流程隔离边界。
  - [x] 先写失败测试：覆盖高质量继续 page 3、连续低质停止并跳过 page 3、orchestrator 传递 adaptive 参数。
  - [x] 实现 live gate 自适应评分与状态落盘，保持默认固定计划行为不变。
  - [x] 更新 broad mode stage command plan，把 strategy/state/page-quality/seen 文件传给 live gate。
  - [x] 跑聚焦测试、编译检查和 diff hygiene。
  - Review：已补 `docs/superpowers/specs/2026-05-24-maimai-broad-recall-adaptive-design.md`，明确 `max_pages` 只代表初始 probe 页数，adaptive live gate 必须用 `unit_max_pages` 在执行中继续 page 3-N，不能要求后续页预先出现在 wave plan。`scripts/maimai_ai_infra_search_live_gate.py` 已在传入 adaptive 参数时按每个成功页即时评分、写入 `adaptiveQuality`、刷新 `page-quality/state/seen`，高质量/观察继续翻页，连续低质或 `unit_max_pages` exhausted 时跳过当前 unit 剩余页；未传 adaptive 参数时仍按固定 plan 执行。`scripts/maimai_campaign_orchestrator.py` 的 broad mode 已把 strategy、adaptive state、seen candidates 和 page-quality 路径传给 live gate，并移除后置 `evaluate_page_quality` stage，避免执行完才评估。配套补充了 manifest schema 兼容、BOM JSONL、失败页不计入页质摘要等回归。验证：`python -m pytest tests\test_maimai_ai_infra_search_live_gate.py tests\test_maimai_broad_recall_adaptive.py tests\test_maimai_campaign_orchestrator.py tests\test_maimai_campaign_search_plan.py tests\test_maimai_search_live_standardize.py -q` -> `72 passed`；`python -m pytest tests\test_maimai_ai_infra_search_live_gate.py tests\test_maimai_broad_recall_adaptive.py tests\test_maimai_campaign_orchestrator.py tests\test_maimai_campaign_search_plan.py tests\test_maimai_talent_search_campaign_skill.py tests\test_maimai_search_live_standardize.py -q` -> `83 passed`；`python -m py_compile scripts\maimai_ai_infra_search_live_gate.py scripts\maimai_campaign_orchestrator.py scripts\maimai_broad_recall_adaptive.py scripts\maimai_ai_infra_campaign.py scripts\maimai_campaign_search_plan.py scripts\maimai_search_live_standardize.py` 通过；`git diff --check` 通过；`python -m pytest tests scripts -q` -> `858 passed, 1 warning`，warning 为既有 `scripts/test_boss.py` event loop deprecation。本轮只改离线代码/测试/文档，未执行真实脉脉搜索，未写 `data/talent.db`。

- [x] 调查 `broad_recall_adaptive_v1` 本次无人值守执行是否真实实现在线动态扩页（2026-05-24）。
  - [x] 核对 campaign plan、wave plan、raw/progress 与报告中的实际页数。
  - [x] 追踪 `build_broad_recall_search_units`、wave 编译、live gate 和 page-quality 阶段调用链。
  - [x] 判断 6 个 wave/272 页是否为预先固定计划，还是执行中根据页质动态生成。
  - [x] 输出根因、影响范围和后续修正建议。
  - Review：用户判断成立。本轮实际是“2 页 probe-only + 后置页质评估”，不是在线动态扩页。证据：`state/search-wave-plan.json` 在 12:13 已固定 `wave_count=6/page_count=272/wave_pages=50/50/50/50/50/22`，136 个 batch 全部 `start_page=1/max_page=2/max_pages=2/probe_pages=2/unit_max_pages=15`；canonical raw 为 136 个 unit 各 2 页，`raw_units_gt_2_count=0`；`reports/page-quality*.jsonl` 与 `state/adaptive-unit-state-search-wave-*.json` 在搜索完成后生成，合并状态中 127 个 unit 已为 `active/observing` 且 `next_page=3`，但没有任何 page 3 raw。代码链路上，`build_broad_recall_search_units` 把 `max_pages` 设为 `probe_pages`，`plan-waves` 只按 `max_pages` 生成固定 wave，`maimai_ai_infra_search_live_gate` 只按 plan 的 `start_page..max_page` 执行，`evaluate_page_quality_run` 只写状态和报告，orchestrator 后续直接进入 import/detail/summary，没有消费 `adaptive-unit-state` 生成 page 3-N follow-up wave。影响：现有 3783 人和 1004 详情有效，但召回深度低于原设计；短期可基于现有 page-quality/state 生成 follow-up wave 从 page 3 继续，高质量/观察 unit 继续、低质量 unit 跳过；中期需把 page-quality 反馈接入 live/orchestrator 执行循环并补回归测试。

- [x] 腾讯游戏 AI 岗位 broad recall 脉脉扩库寻访计划与无人值守执行（2026-05-24）：读取 Feishu Wiki `SQdPw1CixilmOwktgZtcyZyUnqd`，整理为本地寻访业务需求，并用 `strategy_mode=broad_recall_adaptive_v1` 生成扩库 campaign 计划；搜索计划确认后进入无人值守执行。
  - [x] 整理业务需求到 `docs/business-requirements/`。
  - [x] 生成 campaign 合同：`requirements.json`、`strategy.json`、`run-policy.json`、`campaign-manifest.json`、`search-implementation-plan.md`。
  - [x] 编译 `search-plan.json`、`search-units.jsonl` 和 wave plan。
  - [x] 校验实验模式护栏、query-only filters、预算拆分和 workflow status。
  - [x] 写回 Review。
  - [x] 等待用户确认后再进入真实脉脉执行。
  - [x] 已收到确认，进入无人值守预检。
  - [x] 平台登录阻断处理后恢复真实搜索执行。
  - [x] `search-wave-003` 验证码/API 阻断处理后继续无人值守搜索。
  - [x] 完成 `search-wave-001` 到 `search-wave-006` 全部 272 页搜索、标准化、页质评估和 Campaign DB clean apply。
  - [x] 完成详情优先级、11 个详情 pack、1004 个详情抓取 job、详情 dry-run/apply 和 broad recall 摘要。
  - Blocked：已写入确认并启动 CDP 专用浏览器，`http://127.0.0.1:9888/json/version` 可用，session manifest 为 `data/campaigns/tencent-games-ai-100hc-broad-recall-2026-05-24/state/browser-bootstrap.json`。预检发现当前 target 为 `https://maimai.cn/platform/login`，不是人才银行页，按 workflow 停机，不执行真实搜索。中断证据：`reports/interruption-search-preflight-login-2026-05-24.json`；恢复计划：`state/continuation-plan.json`；当前状态：`search_preflight/blocked`，原因 `login`，`completed=0/272`。恢复条件：在已启动浏览器完成脉脉登录，进入人才银行页，并在该页手动执行一次搜索以刷新 `/api/ent/v3/search/basic` 被动模板，然后执行 `python -m scripts.maimai_campaign_orchestrator resume --campaign-root data/campaigns/tencent-games-ai-100hc-broad-recall-2026-05-24` 查看恢复入口；真实执行命令已保存在 `stage_argv`。
  - Blocked：用户已在人才银行页完成一次手动搜索后恢复真实执行；`search-wave-001` 完成 `50` 页、`25` 个 batch、`1500` 联系人，`search-wave-002` 完成 `50` 页、`25` 个 batch、`1444` 联系人；`search-wave-003` 在 `unit-000075 page 1` 触发 `captcha_api`/HTTP 429，按 workflow 硬停机，不继续 `search-wave-004`。已标准化 checkpoint `148/272` 页到 `raw/search/unit-*/page-*.json`，未导入 Campaign DB、未写主库。中断证据：`reports/interruption-search-wave-003-captcha-api-2026-05-24.json`；恢复计划：`state/continuation-plan.json`；当前状态：`search_wave_execution/blocked`，原因 `captcha_api`，`completed=148/272`。恢复条件：负责人处理验证码/安全提示，回到人才银行页，并手动执行一次搜索刷新 `/api/ent/v3/search/basic` 被动模板后，从 `search-wave-003` 继续。
  - Review：用户处理验证码/API 阻断后，已用 `state/search-wave-003-resume-after-captcha-plan.json` 只补 `unit-000075` 两页，保留原中断 run 不覆盖；随后完成 `search-wave-004/005/006`。搜索阶段 canonical raw 共 `272` 页，page-quality 分布 `good=94 / observe=138 / low=40`，列表 live contacts seen `7984`，Campaign DB apply 后 `candidates=3783/source_profiles=3783/candidate_details=3783/pending_merges=0/sync_conflicts=0` 且 `PRAGMA integrity_check=ok`。详情优先级为 `detail_p0=26/detail_p1=978/detail_p2=90/skip=2689`；已按 A+B 生成并执行 11 个详情 pack，共 `1004` 个 job，详情 dry-run/apply 全部 clean，Campaign DB 中 `maimai_detail_capture=1004`。最终摘要：`reports/unattended-run-summary.json`、`reports/unattended-run-summary.md`、`reports/broad-recall-summary.json`、`reports/broad-recall-summary.md`；campaign status 为 `completed_unattended_broad_recall`。本轮未写主库 `data/talent.db`，主库同步仍为 `manual_only`。
  - Review：Feishu Wiki 已通过 `lark-cli docs +fetch --api-version v2` 读回，源文档 `document_id=Ci0sdghrAo7q2Tx2hINc2967nNg/revision_id=10`。业务需求已写入 `docs/business-requirements/09-tencent-games-ai-infra-algorithm-product-100hc.md`，明确腾讯游戏 AI Infra/算法/数据/评测/产品 100HC、3 年以上经验、AI Infra 与多模态公司池、must-have/nice-to-have/排除项和缺失字段。campaign root 为 `data/campaigns/tencent-games-ai-100hc-broad-recall-2026-05-24/`，显式 `strategy_mode=broad_recall_adaptive_v1`、`search_intent=talent_pool_expansion`、`account_day_page_guardrail=500`、`campaign_page_budget=null`、`detail_concurrency=4`、`auto_rank_after_detail_apply=false`、`auto_publish_feishu_delivery_after_detail_rank=false`、`allow_feishu_delivery_publish=false`、`allow_main_db_write=false`。离线编译生成 `136` 个 search units，初始探测 `272` 页，拆为 `6` 个 wave：`50/50/50/50/50/22`；所有 unit 均为 query-only，`allcompanies=""`、`positions=""`、`query_relation=0`，首尾 query 分别为 `华为盘古 大模型 多模态 训练平台 推理` 和 `Happyhorse AI 产品 大模型 AIGC 多模态`。workflow status 停在 `S2_search_plan_compiled/draft_pending_search_plan_confirmation`，`search_plan_confirmed=false`，未执行真实脉脉请求、未写 Campaign DB、未写主库。验证：JSON 解析通过；`python -m scripts.maimai_campaign_orchestrator status --campaign-root data\\campaigns\\tencent-games-ai-100hc-broad-recall-2026-05-24` 返回确认点；结构校验 `bad_filters=0`；`python -m pytest tests\\test_maimai_broad_recall_adaptive.py tests\\test_maimai_campaign_search_plan.py tests\\test_maimai_campaign_orchestrator.py -q` -> `39 passed`；`git diff --check -- tasks\\todo.md docs\\business-requirements\\09-tencent-games-ai-infra-algorithm-product-100hc.md data\\campaigns\\tencent-games-ai-100hc-broad-recall-2026-05-24` 通过。
- [x] 脉脉宽召回自适应寻访实验模式实现（2026-05-24）：基于已确认 spec 实现 `strategy_mode=broad_recall_adaptive_v1`，保持原流程默认行为不变。
  - [x] 写入实施计划：`docs/superpowers/plans/2026-05-24-maimai-broad-recall-adaptive-implementation-plan.md`。
  - [x] 新增宽召回自适应策略模块和规则页质评分测试。
  - [x] 将 search plan 与 orchestrator 对显式 `strategy_mode=broad_recall_adaptive_v1` 路由到新实验编排。
  - [x] 实现详情优先级和寻访摘要报告，跳过推荐报告、外联 sheet 和飞书候选人交付包。
  - [x] 更新 skill/workflow 文档合同测试。
  - [x] 跑聚焦测试、全量测试和 diff hygiene，写回 Review。
  - Review：新增 `scripts/maimai_broad_recall_adaptive.py`，提供 `strategy_mode=broad_recall_adaptive_v1` 检测、宽召回 search units、规则页质评分、unit 状态、详情优先级、寻访摘要报告和 CLI 子命令。`scripts/maimai_campaign_search_plan.py` 仅在显式 broad mode 下生成 adaptive unit；`scripts/maimai_campaign_orchestrator.py` 仅在 broad mode 下改走 `evaluate_page_quality -> detail_priority -> detail_pack -> broad_recall_summary`，并跳过 detailed rank、delivery report、outreach package 和 Feishu delivery package；旧默认流程保持不变。`skills/maimai-talent-search-campaign/SKILL.md` 与 `agents/workflows/maimai-unattended-campaign/AGENT.md` 已补实验模式合同。验证：`python -m pytest tests/test_maimai_broad_recall_adaptive.py tests/test_maimai_campaign_search_plan.py tests/test_maimai_campaign_orchestrator.py tests/test_maimai_talent_search_campaign_skill.py -q` -> `50 passed`；`python -m pytest tests scripts -q` -> `852 passed, 1 warning`；`python -m py_compile scripts/maimai_broad_recall_adaptive.py scripts/maimai_campaign_orchestrator.py scripts/maimai_campaign_search_plan.py` 通过；`git diff --check` 通过。warning 为既有 `scripts/test_boss.py` event loop deprecation。

- [x] 脉脉宽召回自适应寻访实验模式设计（2026-05-24）：讨论并固化 `strategy_mode=broad_recall_adaptive_v1`，作为不替换原流程的并行实验 mode。
  - [x] 确认目标：在不明显牺牲相关性的前提下最大化脉脉扩库收益。
  - [x] 确认方案 B：新增实验 mode，共用搜索、导入、详情、通知和恢复等底层原子能力。
  - [x] 确认搜索策略：宽召回、自适应翻页、规则页质评分、无 campaign 总预算。
  - [x] 确认执行护栏：500 页为单账号单日平台护栏，换账号由用户手动完成，workflow 只做阻断识别和恢复。
  - [x] 确认产出范围：列表粗筛只决定详情优先级，详情 apply 后只生成寻访摘要报告，不做人选推荐和外联 sheet。
  - Review：设计文档已写入 `docs/superpowers/specs/2026-05-24-maimai-broad-recall-adaptive-design.md`。本轮只产出设计，不进入实现；下一步需用户 review spec 后再写实施计划。

- [x] 08 混元多模态数据工程师 JD 人才库推荐（2026-05-23）：按 `docs/business-requirements/08-hunyuan-multimodal-data-engineer.md` 读取完整 JD，基于本地 `data/talent.db` 只读生成岗位画像、评分卡、Top30 推荐报告和外联表，并直接发布到飞书 Wiki `JD需求交付`，发布后用飞书消息通知群。
  - [x] 确认 08 JD、`jd-talent-delivery` workflow、输出目录、主库只读边界、飞书 Wiki 与默认通知群。
  - [x] 建立独立 `data/output/` 运行目录并复制 JD。
  - [x] 基于 08 完整 JD 和既有 `hunyuan-08-multimodal-data-engineer-2026-05-22` 参考策略生成岗位画像和评分卡。
  - [x] 只读匹配 `data/talent.db`，产出粗筛、精排、推荐报告和外联表。
  - [x] 生成 Feishu publish manifest，完成 dry-run 后真实发布并回读 Wiki/Doc/Sheet。
  - [x] 发送飞书消息通知并校验消息发送结果。
  - [x] 校验输出完整性、推荐结果质量、乱码/tracking URL 和敏感产物未上传，写回 Review。
  - Review：输出目录 `data/output/08-hunyuan-multimodal-data-engineer-2026-05-23/`，岗位画像和评分卡已按 08 完整 JD + `hunyuan-08-multimodal-data-engineer-2026-05-22` 策略补强，聚焦多模态数据管线、TB/PB 分布式处理、Spark/Ray/Flink、Python/Linux、数据质量、元数据、版本管理和可追溯。基于主人才库全量 `13332` 人只读匹配，精排 `112` 人，Top30 为 `A=2/B=28/C=0/淘汰=0`，质量门禁 passed。飞书 Wiki 目录 `https://sq8org1v4k6.feishu.cn/wiki/KRFdwUAAnielGSkdXcicUjxAnDd` 已发布并回读 4 个子节点：JD `F3G0dV28gofUPZx8hMYcrY1HncH`、岗位画像 `BLFVdtYGLoPu1tx0EFDcEXLonDh`、推荐报告 `XOs1ducBGovbP5xwBPjcoS1TnTX`、外联表 `NXz8s8fsrhxsYWt5kOMcGx1MnTd`；IM 通知已发送到 `JD需求协同` 群 `oc_632ba22d46d3900d26ada803b2cfa196`，消息 `om_x100b6e20a4bb20b8b4a34f70946271d`。验证：`python -m pytest tests\test_jd_talent_delivery_feishu.py tests\test_jd_talent_delivery_match.py -q` -> `49 passed`；`python -m py_compile scripts\jd_talent_delivery_feishu.py scripts\jd_talent_delivery_match.py scripts\jd_talent_delivery.py scripts\jd_talent_delivery_profile.py scripts\jd_talent_delivery_scorecard.py` 通过；输出 JSON 全部可解析、外联 CSV `30` 行、敏感/乱码/tracking 扫描无命中；`git diff --check -- tasks\todo.md memory\error-log.md data\output\08-hunyuan-multimodal-data-engineer-2026-05-23` 通过。期间发现本机 `lark-cli doctor/auth status` 不支持 `--format`，已改用当前 CLI 语法并记录到 `memory/error-log.md`。

- [x] JD talent delivery 全流程自动推进边界加固（2026-05-23）：检查并更新 `agents/workflows/jd-talent-delivery/AGENT.md`，确保 JD 输入齐全且中间无错误时，S0-S8 从头执行到尾，中间不询问是否继续、不要求人工二次确认。
  - [x] 补文档合同测试，覆盖全流程连续执行、dry-run/readback/质量门禁通过即自动推进、禁止阶段间人工二次确认。
  - [x] 更新 canonical workflow 全局执行规则和 S0-S8 推进语义。
  - [x] 同步 `skills/jd-talent-delivery/SKILL.md` 自动交接摘要。
  - [x] 跑聚焦测试和 diff 检查，写回 Review。
  - Review：`agents/workflows/jd-talent-delivery/AGENT.md` 新增“连续执行规则”，明确输入齐全且门禁通过时按 S0->S8 连续执行到完成，阶段成功输出即进入下一阶段授权，不得在 S1-S8 之间询问是否继续、是否发布或是否发送通知；dry-run、回读和质量门禁都是自动验证门禁，通过即继续、失败才停。S0 的能力检查已改为运行时校验和错误证据落盘，不再写成人工确认能力；安全/停机条件补充了正常路径不包含 `--yes` 高风险写操作，遇到 `confirmation_required` 或要求 `--yes` 时停机而非插入二次确认。`skills/jd-talent-delivery/SKILL.md` 同步输入齐全后自动从 S0 连续执行到 S8、不需要阶段间人工二次确认。验证：先跑 RED 得到 2 个预期失败；实现后 `python -m pytest tests\test_jd_talent_delivery_workflow.py tests\test_jd_talent_delivery_skill.py -q` -> `15 passed`；`git diff --check -- ...` 通过。

- [x] JD talent delivery 完成通知默认发群改造（2026-05-23）：消息模板和正文保持不变，workflow 任务完成后默认用飞书 user 身份发到 `JD需求协同` 群，并发送一条测试消息让用户确认。
  - [x] 先补回归测试，锁定默认通知目标为 `JD需求协同` 群、发送命令使用 `--as user --chat-id`，且消息模板不变。
  - [x] 修改 `scripts/jd_talent_delivery_feishu.py` 默认通知解析逻辑，保留显式 `--notify-user-id` / `--notify-chat-id` 覆盖。
  - [x] 同步 `agents/workflows/jd-talent-delivery/AGENT.md` 和 `skills/jd-talent-delivery/SKILL.md` 的完成通知合同。
  - [x] 跑聚焦测试、编译和 diff 检查。
  - [x] 搜索 `JD需求协同` 群并用 user 身份发送测试消息，记录结果。
  - Review：`scripts/jd_talent_delivery_feishu.py` 已将默认完成通知目标从授权用户 open_id 改为 `JD需求协同` 群：发布回读通过后先执行 `im +chat-search --as user --query JD需求协同`，精确匹配群名并解析 `chat_id`，再用 `im +messages-send --as user --chat-id` 发送，显式 `--notify-user-id` / `--notify-chat-id` 覆盖逻辑保留。`agents/workflows/jd-talent-delivery/AGENT.md` 和 `skills/jd-talent-delivery/SKILL.md` 已同步默认群通知合同，消息模板函数未改。验证：先跑 RED 得到 3 个预期失败；实现后 `python -m pytest tests\test_jd_talent_delivery_feishu.py tests\test_jd_talent_delivery_workflow.py tests\test_jd_talent_delivery_skill.py -q` -> `51 passed`；`python -m py_compile scripts\jd_talent_delivery_feishu.py` 通过；`git diff --check -- ...` 通过。真实飞书测试：搜索到 `JD需求协同` 群 `chat_id=oc_632ba22d46d3900d26ada803b2cfa196`，已用 user 身份发送测试消息，`message_id=om_x100b6e20362990acb26ffa53145fa15`。

- [x] 07 混元数据算法负责人-语音方向 JD 人才库推荐（2026-05-23）：按 `docs/business-requirements/07-hunyuan-data-algorithm-lead-speech.md` 读取完整 JD，基于本地 `data/talent.db` 只读生成岗位画像、评分卡、Top30 推荐报告和外联表，并直接发布到飞书 Wiki `JD需求交付`，发布后用飞书消息通知用户。
  - [x] 建立独立 `data/output/` 运行目录并复制 JD。
  - [x] 基于 07 JD 和既有 `hunyuan-07-data-algorithm-speech-2026-05-22` 参考策略生成岗位画像和评分卡。
  - [x] 只读匹配 `data/talent.db`，产出粗筛、精排、推荐报告和外联表。
  - [x] 生成 Feishu publish manifest，完成 dry-run 后真实发布并回读 Wiki/Doc/Sheet。
  - [x] 发送飞书消息通知用户并校验消息发送结果。
  - [x] 校验输出完整性、推荐结果质量、乱码/tracking URL 和敏感产物未上传，写回 Review。
  - Review：输出目录 `data/output/07-hunyuan-data-algorithm-lead-speech-2026-05-23/`，岗位画像和评分卡已按 07 完整 JD + `hunyuan-07-data-algorithm-speech-2026-05-22` 策略补强，聚焦 ASR/语音/音频数据算法、音频质量评估、数据清洗、标注、数据合成和数据 pipeline。基于主人才库全量 `13332` 人只读匹配，精排 `1317` 人，Top30 为 `A=1/B=29/C=0/淘汰=0`，质量门禁 passed。飞书 Wiki 目录 `https://sq8org1v4k6.feishu.cn/wiki/ClRfwtTTfi5sCrkGYjqcWF9bntb` 已发布并回读 4 个子节点：JD `Ce1Md6UAaoTQ9SxjgtkcMwVunwg`、岗位画像 `UcYkdiB3Por2XWxoU3bcK3r5n5g`、推荐报告 `HKtRdQzPLocXhgxjFPUcRo9Rn7c`、外联表 `B8TSs3ykvhtp2ZtLMN0cqyiMnff`；IM 通知已发送到 `ou_81c032a629f9bb197fd65e8134ecf9ac`。验证：`python -m pytest tests\test_jd_talent_delivery_feishu.py tests\test_jd_talent_delivery_match.py -q` -> `49 passed`；`python -m py_compile scripts\jd_talent_delivery_feishu.py scripts\jd_talent_delivery_match.py scripts\jd_talent_delivery.py scripts\jd_talent_delivery_scorecard.py` 通过；输出 JSON 全部可解析、外联 CSV `30` 行且无 `trackable_token`；`git diff --check -- ...` 通过。

- [x] 06 混元数据算法负责人-3D方向 JD 人才库推荐（2026-05-23）：按 `docs/business-requirements/06-hunyuan-data-algorithm-lead-3d.md` 读取完整 JD，基于本地 `data/talent.db` 只读生成岗位画像、评分卡、Top30 推荐报告和外联表，并直接发布到飞书 Wiki `JD需求交付`，发布后用飞书消息通知用户。
  - [x] 建立独立 `data/output/` 运行目录并复制 JD。
  - [x] 基于 06 JD 和既有 `hunyuan-06-data-algorithm-3d-2026-05-22` 参考策略生成岗位画像和评分卡。
  - [x] 只读匹配 `data/talent.db`，产出粗筛、精排、推荐报告和外联表。
  - [x] 生成 Feishu publish manifest，完成 dry-run 后真实发布并回读 Wiki/Doc/Sheet。
  - [x] 发送飞书消息通知用户并校验消息发送结果。
  - [x] 校验输出完整性、推荐结果质量、乱码/tracking URL 和敏感产物未上传，写回 Review。
  - Review：输出目录 `data/output/06-hunyuan-data-algorithm-lead-3d-2026-05-23/`，岗位画像和评分卡已按 06 完整 JD + `hunyuan-06-data-algorithm-3d-2026-05-22` 策略补强，聚焦 3D/多模态数据算法、embedding/Caption、质量评估、去重聚类、数据合成和数据 pipeline。基于主人才库全量 `13332` 人只读匹配，精排 `1307` 人，Top30 为 `A=3/B=27/C=0/淘汰=0`，质量门禁 passed。飞书 Wiki 目录 `https://sq8org1v4k6.feishu.cn/wiki/EoOMw1JWTiqdnwkejnEcOvOSnTf` 已发布并回读 4 个子节点：JD `JcNYdpeAuoyecKx0t8OcGh1onHd`、岗位画像 `GmCYdlOBjo4kgUx8yq9co0smnuh`、推荐报告 `Abjmd4tIUoVrIxxyVtZccTxsnbe`、外联表 `VcT8sUI5HhiNXGt6tfqcM7j5nY2`；IM 通知已发送到 `ou_81c032a629f9bb197fd65e8134ecf9ac`。验证：`python -m pytest tests\test_jd_talent_delivery_feishu.py tests\test_jd_talent_delivery_match.py -q` -> `49 passed`；`python -m py_compile scripts\jd_talent_delivery_feishu.py scripts\jd_talent_delivery_match.py scripts\jd_talent_delivery.py scripts\jd_talent_delivery_scorecard.py` 通过；输出 JSON 全部可解析、外联 CSV `30` 行且无 `trackable_token`；`git diff --check -- ...` 通过。

- [x] 05 混元大模型后训练算法工程师/专家 JD 人才库推荐（2026-05-23）：按 `docs/business-requirements/05-hunyuan-llm-post-training-algorithm-expert.md` 读取完整 JD，基于本地 `data/talent.db` 只读生成岗位画像、评分卡、Top30 推荐报告和外联表，并直接发布到飞书 Wiki `JD需求交付`，发布后用飞书消息通知用户。
  - [x] 建立独立 `data/output/` 运行目录并复制 JD。
  - [x] 基于 05 JD 和既有 `hunyuan-05-llm-post-training-algorithm-2026-05-22` 参考策略生成岗位画像和评分卡。
  - [x] 只读匹配 `data/talent.db`，产出粗筛、精排、推荐报告和外联表。
  - [x] 生成 Feishu publish manifest，完成 dry-run 后真实发布并回读 Wiki/Doc/Sheet。
  - [x] 发送飞书消息通知用户并校验消息发送结果。
  - [x] 校验输出完整性、推荐结果质量、乱码/tracking URL 和敏感产物未上传，写回 Review。
  - Review：输出目录 `data/output/05-hunyuan-llm-post-training-algorithm-expert-2026-05-23/`，岗位画像和评分卡已按 05 完整 JD + `hunyuan-05-llm-post-training-algorithm-2026-05-22` 策略补强；全库只读粗筛 13332 人、精排 1274 人，Top30 为 `A=3/B=27/C=0/淘汰=0`，质量门禁 passed。飞书 Wiki 目录 `https://sq8org1v4k6.feishu.cn/wiki/ImaxwnldaiAWKGkayqpcSAKPn0g` 已发布并回读 4 个子节点：JD `BXJodX8oRoN47zxRloxceyZSnXd`、岗位画像 `O96xd16jaoilhRxe3QpcsU8Mnue`、推荐报告 `L6IEdRr5joy6FhxJQHAchoRongf`、外联表 `CH2Ksq6BahlA63tEEhhcZg7Cn2f`；IM 通知已发送到 `ou_81c032a629f9bb197fd65e8134ecf9ac`。期间修复发布器两处复用问题：Sheet 回读支持多段 rich text cell，IM 通知改用直接 Node runner 发送多行中文。验证：`python -m pytest tests\test_jd_talent_delivery_feishu.py tests\test_jd_talent_delivery_match.py -q` -> `49 passed`；`python -m py_compile scripts\jd_talent_delivery_feishu.py scripts\jd_talent_delivery_match.py` 通过；输出 JSON 全部可解析；发布包扫描无 tracking/raw/DB 路径或乱码标记；`git diff --check -- ...` 通过；`python -m pytest tests scripts -q` -> `841 passed, 1 warning`。

- [x] JD talent delivery 飞书完成通知与 Sheet 防乱码发布改造（2026-05-23）：把任务结束后的飞书 IM 通知固化为 workflow 标准步骤，并把外联表发布从 CSV Drive import 改为 `sheets +create` + UTF-8 JSON `sheets +write`，从机制上避免中文乱码。
  - [x] 更新 workflow/skill contract：新增完成通知步骤、固定消息模板、成果物和停机条件；明确禁止外联表使用 `drive +import --type sheet`。
  - [x] 改造 `scripts/jd_talent_delivery_feishu.py`：外联表创建空 Sheet 后写入 CSV rows；发布完成后生成通知文本并用 `im +messages-send` 推送。
  - [x] 补充/调整回归测试：覆盖无 CSV import、UTF-8 JSON 写入、通知模板、默认通知目标和发送结果落盘。
  - [x] 更新 `tasks/lessons.md` 和 `memory/error-log.md`，记录本次用户纠正与根因。
  - [x] 跑聚焦测试、编译和 diff 检查，并在本任务写 Review。
  - Review：`agents/workflows/jd-talent-delivery/AGENT.md` 新增 S8 飞书完成通知，固化 `im +messages-send` 方式和消息模板；`skills/jd-talent-delivery/SKILL.md` 同步输出产物与发布边界。`scripts/jd_talent_delivery_feishu.py` 已禁止外联表 CSV Drive import 路径，改为 `sheets +create`、解析 CSV 为二维数组、`sheets +write --values` 分块写入，并对 Sheets JSON payload 优先使用显式 Node CLI runner；发布/回读通过后写入 `feishu/im-notification-message.txt`、`feishu/im-notification-results.json` 并发送 IM。验证：`python -m pytest tests\test_jd_talent_delivery_feishu.py tests\test_jd_talent_delivery_workflow.py tests\test_jd_talent_delivery_skill.py -q` -> `49 passed`；`python -m pytest tests\test_jd_talent_delivery_match.py tests\test_jd_talent_delivery_feishu.py tests\test_jd_talent_delivery_cli.py tests\test_jd_talent_delivery_workflow.py tests\test_jd_talent_delivery_skill.py tests\test_jd_talent_delivery_scorecard.py tests\test_jd_talent_delivery_profile.py -q` -> `74 passed`；`python -m py_compile scripts\jd_talent_delivery_feishu.py` 通过；`git diff --check -- ...` 通过。

- [x] 04 混元数据管理平台技术负责人 JD 人才库推荐重试（2026-05-23）：按 `docs/business-requirements/04-hunyuan-data-management-platform-tech-lead.md` 读取 JD，基于本地 `data/talent.db` 只读生成岗位画像、评分卡、Top30 推荐报告和外联表，并直接发布到飞书 Wiki `JD需求交付`，发布后用飞书消息通知用户；因 JD 正文为“待补充”，本轮结果必须标记低置信边界，不写强结论。
  - [x] 确认 04 JD、复用工作流入口、输出目录、Wiki 父节点和 IM 通知目标。
  - [x] 建立独立 `data/output/` 运行目录并复制 JD。
  - [x] 基于 04 JD 和既有 04 参考策略生成低置信岗位画像和评分卡。
  - [x] 只读匹配 `data/talent.db`，产出粗筛、精排、推荐报告和外联表。
  - [x] 生成 Feishu publish manifest，完成 dry-run 后真实发布并回读 Wiki/Doc/Sheet。
  - [x] 发送飞书消息通知用户并校验消息发送结果。
  - [x] 校验输出完整性、推荐结果质量、乱码/tracking URL 和敏感产物未上传，写回 Review。

- [x] 03 混元数据标注平台技术负责人 JD 人才库推荐（2026-05-23）：按 `docs/business-requirements/03-hunyuan-data-labeling-platform-tech-lead.md` 读取 JD，基于本地 `data/talent.db` 只读生成岗位画像、评分卡、Top30 推荐报告和外联表，并直接发布到飞书 Wiki `JD需求交付`；因 JD 正文为“待补充”，本轮结果必须标记低置信边界，不写强结论。
  - [x] 建立独立 `data/output/` 运行目录并复制 JD。
  - [x] 基于 03 JD 和既有 `hunyuan-03-data-labeling-platform-tech-lead-2026-05-22` 参考策略生成低置信岗位画像和评分卡。
  - [x] 只读匹配 `data/talent.db`，产出粗筛、精排、推荐报告和外联表。
  - [x] 生成 Feishu publish manifest，完成 dry-run 后真实发布并回读 Wiki/Doc/Sheet。
  - [x] 校验输出完整性、推荐结果质量、乱码/tracking URL 和敏感产物未上传。

- [x] JD talent delivery 匹配/发布工作流优化（2026-05-23）：不依赖 campaign `strategy.json` 或现成 `*rank*.json`，把 `jd_talent_delivery_match` 补强为可独立从 `scorecard.json` + `data/talent.db` 完成详情后精排、质量门禁和飞书发布前校验。
  - [x] 先补回归测试：过多 `must_have` 不再稀释强相关候选人、公司/产品别名可展开、脉脉 URL 去除 `trackable_token`、TopN/CSV/外联角度/敏感路径/乱码门禁能阻断异常。
  - [x] 参考 `maimai_campaign_rank` 和详情后 delivery/outreach 脚本，完善匹配逻辑：title level、公司别名展开、详情证据、方向标签、外联角度、风险与优先级。
  - [x] 增加发布前质量校验：scorecard 质量、TopN 数量与分层、CSV 可解析、候选人关键字段、敏感 artifact、tracking URL、mojibake、Sheet 回读关键列。
  - [x] 强化 Feishu/lark-cli 执行：集中 argv runner、发布后 readback 校验，并记录 range-limited `sheets +write` 恢复路径。
  - [x] 更新 `agents/workflows/jd-talent-delivery/AGENT.md` 和 `skills/jd-talent-delivery/SKILL.md`，明确不要求 campaign strategy/rank 前置。
  - [x] 跑聚焦测试、必要全量子集和 `git diff --check`，把 Review 写回任务台账；若出现非显而易见错误，补 `memory/error-log.md`。

- [x] 02 混元大模型数据产品专家/leader JD 人才库推荐（2026-05-23）：按 `docs/business-requirements/02-hunyuan-llm-data-product-lead.md` 读取 JD，基于本地 `data/talent.db` 只读生成岗位画像、评分卡、Top30 推荐报告和外联表，并直接发布到飞书 Wiki `JD需求交付`。
  - [x] 建立独立 `data/output/` 运行目录并复制 JD。
  - [x] 基于 02 JD 和既有 `hunyuan-02-llm-data-product-lead-2026-05-22` strategy 生成岗位画像和评分卡。
  - [x] 只读匹配 `data/talent.db`，产出粗筛、精排、推荐报告和外联表。
  - [x] 生成 Feishu publish manifest，完成 dry-run 后真实发布并回读 Wiki/Doc/Sheet。
  - [x] 校验输出完整性、推荐结果质量和敏感产物未上传。

- [x] 01 混元大模型数据策略负责人 JD 人才库推荐（2026-05-23）：按 `docs/business-requirements/01-hunyuan-llm-data-strategy-lead.md` 读取 JD，基于本地 `data/talent.db` 只读生成岗位画像、评分卡、Top30 推荐报告和外联表，并发布到飞书 Wiki `JD需求交付`。
  - [x] 建立独立 `data/output/` 运行目录并复制 JD。
  - [x] 生成岗位画像和评分卡。
  - [x] 只读匹配 `data/talent.db`，产出粗筛、精排、推荐报告和外联表。
  - [x] 生成 Feishu publish manifest 并复用既有 Wiki 父节点真实发布。
  - [x] 校验输出完整性和推荐结果质量。

- [x] 混元 8JD 详情后主库级重新精排（2026-05-23）：基于已写入 2648 条详情后的 `data/talent.db`，重跑 8 个 JD 的 `maimai_campaign_rank --mode detailed`，并与 2026-05-22 旧精排结果对比。
  - [x] 运行 8 个 campaign strategy 的主库 detailed rank，输出到新的 `data/output/` 目录。
  - [x] 汇总每个 JD 的 A/B/C/淘汰数量和 Top10。
  - [x] 对比详情写入前后的 A/B/C 数量变化和 Top 候选人变化。
  - [x] 校验输出 JSON/Markdown 可读，并更新任务台账 Review。

- [x] 混元 8JD ABC 详情结果写入主库（2026-05-23）：用户要求“下一步写入主库”，基于 27 个 clean dry-run capture 顺序 apply 到 `data/talent.db`。
  - [x] 写入前备份 `data/talent.db`，并验证备份可读与 `PRAGMA integrity_check=ok`。
  - [x] 记录写入前主库基线：候选人/来源/详情表计数、已有 `maimai_detail_capture` 数量。
  - [x] 按 `detail-abc-pack-001` 到 `detail-abc-pack-027` 顺序 apply，使用既有 clean dry-run 作为前置校验。
  - [x] 写入后验证 `PRAGMA integrity_check`、写入人数、`maimai_detail_capture` 增量和 apply 报告。
  - [x] 更新任务台账 Review，保留备份路径、apply 汇总和后续重新精排入口。

- [x] 混元 8JD ABC 三档详情抓取任务与无人值守执行（2026-05-22）：基于主库 detailed rank 的 A/B/C 三档生成去重详情目标池，按 pack 执行脉脉详情 live gate；主库详情写入仍保持人工边界。
  - [x] 确认 `maimai-unattended-campaign` 详情阶段边界、现有 detail live gate/import 接口和主库 ABC rank JSON 字段。
  - [x] 生成 `data/campaigns/hunyuan-8jd-abc-detail-2026-05-22/` 下的目标 manifest、pack JSON、run-policy 和执行摘要。
  - [x] 对 `http://127.0.0.1:9888` 做只读健康检查，确认已有脉脉人才银行页可用且无登录/验证码/安全页阻断。
  - [x] 按 pack 顺序无人值守执行详情抓取；遇到登录、验证码、403/429/432、非 JSON、HTML、模板漂移或 partial capture 时停机并保留 continuation。
    - 执行记录：已从单进程切为显式分片并发 runner；2/3/4 并发均已观察 3 分钟以上，无 stderr、无验证码/429/非 JSON 阻断，并发上限固定为 4。
    - 已启动 `scripts/hunyuan_abc_parallel_supervisor.ps1` 自动补位，最多 4 个活动分片；全部 `detail-abc-pack-001` 到 `detail-abc-pack-027` 已完成。
  - [x] 对完成的 capture 做主库 dry-run 校验；不自动 apply `data/talent.db`，完成后给出明确人工写入入口。
  - [x] 更新任务台账 Review，记录目标数量、pack 数、已完成数量、阻断原因和后续恢复命令。

- [x] 混元 8JD campaign DB -> 主人才库真实同步（2026-05-22）：用户已明确授权 `确认同步混元8JD campaign DB 到主库 data/talent.db`，按已校验 bundle 顺序 apply，先备份再写主库。
  - [x] 创建 `data/talent.db` 的 SQLite 一致备份并验证备份可读。
  - [x] 重新校验 8 个同步 bundle。
  - [x] 按 01 -> 08 顺序 apply 到 `data/talent.db`，记录每个 bundle created/merged/conflicts/skipped。
  - [x] 同步完成后检查 `PRAGMA integrity_check`、候选人/详情/来源计数、`sync_imports`、`sync_conflicts`。
  - [x] 产出真实同步报告，更新后续逐 JD 高精度匹配入口。

- [x] 混元 8JD 主库级逐 JD 详细匹配（2026-05-22）：基于扩充后的 `data/talent.db`，用 8 个 campaign 的 `strategy.json` 分别跑 `maimai_campaign_rank --mode detailed`。
  - [x] 生成 8 个 JD 的主库 detailed rank JSON/Markdown。
  - [x] 汇总每个 JD 的 A/B/C/淘汰数量与 Top 候选人入口。
  - [x] 更新任务台账和验证结果。

- [x] 混元 8JD campaign DB -> 主人才库同步 dry-run 预检（2026-05-22）：已完成 bundle 导出、校验和真实主库 dry-run；真实 `data/talent.db` apply 等待明确授权。
  - [x] 导出并校验 8 个 campaign-local DB 的同步 bundle。
  - [x] 对真实主库 `data/talent.db` 执行逐 bundle dry-run，记录 created/merged/conflicts/skipped。
  - [x] 产出同步预检报告和下一步确认口令。
  - [x] 测试库累计 apply 模拟因耗时过长中止并清理临时 DB；真实写入前改为即时备份 + 顺序 apply + 完整性验证。

- [x] 混元 AI DATA 8JD batch campaign 搜索执行与 Campaign DB 扩库（2026-05-22）：基于 `docs/superpowers/plans/2026-05-22-hunyuan-8jd-maimai-sourcing-plan.md`，已按 8 个 JD campaign root 完成首轮 campaign-local 人才池扩充；主库同步与逐 JD 精排等待单独授权。
  - [x] 生成 batch manifest、`jd-index.json`、8 个 campaign 的 `requirements.json`、`strategy.json`、`run-policy.json`、`campaign-manifest.json` 和 `search-implementation-plan.md`。
  - [x] 编译 8 个 campaign 的 `search-plan.json`、`search-units.jsonl` 和 `state/search-wave-plan.json`。
  - [x] 校验 query-only filters、manifest schema、03/04 低置信度缺失字段、样板词扫描和聚焦测试。
  - [x] 用户已确认 batch 搜索计划，8 个 campaign `run-policy.json` 已标记 `search_plan_confirmed=true`。
  - [x] 已启动 CDP 浏览器和 `extensions/maimai-scraper`，CDP `http://127.0.0.1:9888/json/version` 可用。
  - [x] 修复 `run-campaign` 对 generic JD `strategy.json` 的兼容问题，避免误走 legacy AI Infra schema 校验。
  - [x] 01 岗位 3 个 search wave 已完成标准化、dry-run clean 和 Campaign DB apply；当前 01 Campaign DB `candidates=2662`，list rank 为 `A=0/B=0/C=137/淘汰=2525`。
  - [x] 05 岗位 2 个 search wave 已完成标准化、dry-run clean 和 Campaign DB apply；当前 05 Campaign DB `candidates=1889`，list rank 为 `A=0/B=3/C=154/淘汰=1732`。
  - [x] 08 岗位 2 个 search wave 已完成标准化、dry-run clean 和 Campaign DB apply；当前 08 Campaign DB `candidates=833`，list rank 为 `A=0/B=3/C=61/淘汰=769`。
  - [x] 06 岗位 1 个 search wave 已完成标准化、dry-run clean 和 Campaign DB apply；当前 06 Campaign DB `candidates=907`，list rank 为 `A=0/B=0/C=62/淘汰=845`。
  - [x] 07 岗位 1 个 search wave 已完成标准化、dry-run clean 和 Campaign DB apply；当前 07 Campaign DB `candidates=937`，list rank 为 `A=0/B=1/C=74/淘汰=862`。
  - [x] 02 岗位 1 个 search wave 已完成标准化、dry-run clean 和 Campaign DB apply；当前 02 Campaign DB `candidates=1079`，list rank 为 `A=0/B=38/C=99/淘汰=942`。
  - [x] 03 岗位 `search-wave-001` 验证码恢复后已补齐剩余 28 页，完成标准化、dry-run clean 和 Campaign DB apply；当前 03 Campaign DB `candidates=734`，list rank 为 `A=0/B=0/C=71/淘汰=429`。
  - [x] 04 岗位 `search-wave-001` 在 `http_432` 与 `missing_search_template` 两次阻塞后已恢复并补齐剩余 9 页，完成标准化、dry-run clean 和 Campaign DB apply；当前 04 Campaign DB `candidates=516`，list rank 为 `A=0/B=0/C=27/淘汰=473`。

## Open Items

- 主库 `data/talent.db` 的 campaign DB 同步、ABC 详情写入和详情后全量 detailed rank 均已完成；下一步可基于 `data/output/hunyuan-8jd-main-db-match-after-detail-2026-05-23/` 做 JD 级人工复核与触达队列。
- 03/04 两个 JD 正文仍为“待补充”，本轮只按标题、职级和人才画像制定低置信度扩库策略；后续精排前需要补齐正式 JD 或用交付反馈校准。
- 详情后主库级 detailed rank 已按 `--limit 13332` 全量口径产出；03/04 因 JD 正文缺失仍只可作为低置信候选池，不应用于强推荐结论。

## Recent Done

- 2026-05-22：已修复 `scripts/maimai_ai_infra_pipeline.py` 的 generic JD strategy 导入兼容，并新增 `tests/test_maimai_ai_infra_pipeline.py` 回归；聚焦测试 `58 passed`。
- 2026-05-22：01 岗位首轮 150 页已完成 Campaign DB apply，campaign-local DB 当前 `candidates=2662`，`pending_merges=0`，`sync_conflicts=0`，`PRAGMA integrity_check=ok`。
- 2026-05-22：05 岗位首轮 100 页已完成 Campaign DB apply，campaign-local DB 当前 `candidates=1889`，`pending_merges=0`，`sync_conflicts=0`，`PRAGMA integrity_check=ok`。
- 2026-05-22：08/06/07/02 岗位首轮已完成 Campaign DB apply，当前 campaign-local DB 分别为 `833/907/937/1079` 人，均无 pending/conflict 且 integrity `ok`。
- 2026-05-22：03 岗位 `search-wave-001` 已从 `captcha_api` continuation 恢复并完成 Campaign DB apply，当前 campaign-local DB 为 `734` 人，无 pending/conflict 且 integrity `ok`。
- 2026-05-22：04 岗位 `search-wave-001` 已从 `http_432`/`missing_search_template` continuation 恢复并完成 Campaign DB apply，当前 campaign-local DB 为 `516` 人，无 pending/conflict 且 integrity `ok`。
- 2026-05-22：混元 8JD 主库同步 dry-run 预检完成，8 个 bundle 均校验通过；逐 bundle 对真实主库 dry-run 合计 `exported=9557/created=9392/merged=165/conflicts=0/skipped=0`，真实主库未 apply，`sync_imports` 未新增。
- 2026-05-22：混元 8JD 已真实同步到主库；备份为 `data/backups/talent-main-before-hunyuan-8jd-sync-20260522-211400.db`，apply 合计 `created=7835/merged=1722/conflicts=14/skipped=0`，主库 `candidates=13332/sync_imports=10/integrity=ok`。
- 2026-05-22：混元 8JD 主库级 detailed rank 已生成，汇总见 `data/output/hunyuan-8jd-main-db-match-2026-05-22/main-db-detailed-rank-summary.md`。
- 2026-05-22：已开始核查通用化改造后 AI Infra schema 残留问题，并记录 lesson。
- 2026-05-22：已核对混元数据策略负责人 campaign 的 JD、requirements、strategy、search-units、wave plan、live plan 和执行 raw 证据，未修改 campaign 计划。
- 2026-05-22：已形成并执行 todo token 治理实施计划，详见 `docs/superpowers/plans/2026-05-22-todo-governance.md`。
- 2026-05-21：混元大模型数据策略负责人脉脉寻访继续执行已完成，完整记录见 `tasks/archive/2026-05.md`。
- 2026-05-21：飞书 Wiki JD requirements export、混元寻访计划等已归档，完整记录见 `tasks/archive/2026-05.md`。

## Archive Index

- 2026-05：`tasks/archive/2026-05.md`

## Review

- 2026-05-23 04 混元数据管理平台技术负责人 JD 人才库推荐重试：本轮输出目录为 `data/output/04-hunyuan-data-management-platform-tech-lead-2026-05-23/`。已复制 JD 到 `source/jd.md`；因 JD 正文仍为“待补充”，岗位画像和评分卡显式标记 `low_missing_jd_body`，基于 04 基础信息和既有 04 参考策略校准数据管理平台、元数据、数据治理、数据资产、平台架构和目标公司池。基于主人才库全量 `13332` 人只读匹配，详细评分 `101` 人，Top30 分层为 `A=0/B=4/C=26/淘汰=0`；本轮“推荐”只表示优先深审，不等同强推荐。核心产物包括 `profile/role-deep-dive.md`、`profile/role-profile.json`、`scoring/scorecard.json`、`scoring/coarse-screen.json/md`、`scoring/detailed-rank.json/md`、`reports/talent-recommendation.md/json`、`reports/outreach-queue.csv/md`、`reports/quality-gates.json`、`feishu/publish-manifest.json`、`feishu/publish-results.json`、`feishu/sheet-repair-results.json`、`feishu/im-notification-results.json`。
- 2026-05-23 04 混元数据管理平台技术负责人飞书发布与通知：已发布到 Wiki space `7642607697183001542`，父节点 `AeCAwXBrNivv8rknXQKciRstnHe`（`https://sq8org1v4k6.feishu.cn/wiki/AeCAwXBrNivv8rknXQKciRstnHe`）。子节点 4 个：JD `VMwtdZYE1oKL5Yxa7VUcyE5Znp9` / `Kt7dw0zCgiLhkYkTfgucBuBRnIc`，role profile `TQs9di47cooklBxYr0jcWdOgnZe` / `FkrrwzIlHi4V7KkwpV4cTyEmnre`，recommendation report `CFx7d0wkvopu6Qxqwm0cVXNQnWd` / `NkBMwMuAFiwn2xkzmKYcxSH9ntV`，outreach queue sheet `UAANsuV9ghCdFstkDXncEc0RnTd` / `YjmLwxMKaiiRXpkL8EAcN1eUnbP`。直达链接：推荐报告 `https://sq8org1v4k6.feishu.cn/docx/CFx7d0wkvopu6Qxqwm0cVXNQnWd`，外联表 `https://sq8org1v4k6.feishu.cn/sheets/UAANsuV9ghCdFstkDXncEc0RnTd`。发布后发现 CSV 导入的 Sheet 中文乱码，已用 `sheets +write` 重写 `A1:Q31` 并回读 `A1:Q5` 与本地 CSV 一致；IM 通知已用 user 身份发给当前授权用户，消息 `om_x100b6e26be93b4a0b2c098573eb89a1` 已 `messages-mget` 回读确认。验证：产物完整性 `missing=[]`，质量门禁 `passed`，发布 `published`，Wiki 子节点 `4`，Sheet 修复 `passed`，IM `sent`；聚焦测试 `python -m pytest tests/test_jd_talent_delivery_match.py tests/test_jd_talent_delivery_feishu.py tests/test_campaign_notify.py -q` -> `60 passed`；`git diff --check -- tasks/todo.md memory/error-log.md` 通过。`lark-cli doctor` 提示当前 `1.0.36`，最新 `1.0.39` 可后续更新。

- 2026-05-23 03 混元数据标注平台技术负责人 JD 人才库推荐：本轮输出目录为 `data/output/03-hunyuan-data-labeling-platform-tech-lead-2026-05-23/`。已复制 JD 到 `source/jd.md`，因正文为“待补充”，画像和评分卡显式标记 `low_missing_jd_body`，只使用基础信息、人才画像和 03 参考策略生成低置信候选池。基于主人才库全量 `13332` 人只读匹配，详细评分 `125` 人，Top30 分层为 `A=0/B=22/C=8/淘汰=0`；本轮“推荐”只表示优先深审，不等同强推。核心产物包括 `profile/role-deep-dive.md`、`profile/role-profile.json`、`scoring/scorecard.json`、`scoring/coarse-screen.json/md`、`scoring/detailed-rank.json/md`、`reports/talent-recommendation.md/json`、`reports/outreach-queue.csv/md`、`reports/quality-gates.json`、`feishu/publish-manifest.json`、`feishu/publish-results.json`。
- 2026-05-23 03 混元数据标注平台技术负责人飞书发布：已发布到 Wiki space `7642607697183001542` 的父节点 `Oar3wpU5CikJaRkSWfJcPOC7n0d`（`https://sq8org1v4k6.feishu.cn/wiki/Oar3wpU5CikJaRkSWfJcPOC7n0d`）。父节点下 4 个子节点：JD `VeDKdxTsVoL08YxkbGqcmky6nsf` / `HbTYwbqUmiv9SxkOtOacFWmdn4f`、role profile `GBLddiPNPoPlhwxvl6fcg6Uinkf` / `CJKXwi1qCil9QKkO4UDcFX8enIf`、recommendation report `AQZDdhEv3o4Zxzx4xzRc1hhInQb` / `RT3FwB0ggiFq6YkFccTcA8DGnnd`、outreach queue sheet `UIk3sJ7pzhqvYQtqmBjcKvKBnyf` / `SqkcwvbcSiq6s1krxcIc29ocnCh`。直达链接：JD `https://sq8org1v4k6.feishu.cn/docx/VeDKdxTsVoL08YxkbGqcmky6nsf`，画像 `https://sq8org1v4k6.feishu.cn/docx/GBLddiPNPoPlhwxvl6fcg6Uinkf`，推荐报告 `https://sq8org1v4k6.feishu.cn/docx/AQZDdhEv3o4Zxzx4xzRc1hhInQb`，外联 Sheet `https://sq8org1v4k6.feishu.cn/sheets/UIk3sJ7pzhqvYQtqmBjcKvKBnyf`。验证：`wiki +node-list` 返回 4 个子节点；3 个 Doc outline 读回；Sheet `y8ocjC` 读回 `A1:Z5` 并与本地 CSV 前 17 列一致；发布质量 `passed/top_n=30/outreach_rows=30`；敏感/乱码/tracking 扫描无命中。期间修复了发布器对 `sheets +read` 当前返回结构、URL 单元格对象和尾部空列的兼容，新增回归后 `tests/test_jd_talent_delivery_feishu.py` 为 `32 passed`；聚焦套件 `python -m pytest tests/test_jd_talent_delivery_feishu.py tests/test_jd_talent_delivery_match.py tests/test_jd_talent_delivery_cli.py tests/test_jd_talent_delivery_workflow.py -q` -> `55 passed`，`py_compile` 和 `git diff --check` 通过。`lark-cli doctor` 通过但提示当前 `1.0.36` 可更新到 `1.0.39`。

- 2026-05-23 JD talent delivery 匹配/发布工作流优化：已确认标准路径不依赖 campaign `strategy.json` 或历史 `*rank*.json`。`scripts/jd_talent_delivery_match.py` 现在从 `scorecard.json` + 只读 `data/talent.db` 独立完成粗筛/精排，补齐公司/产品别名展开、title level、详情证据、方向标签、外联角度、宽 `must_have` 防稀释、`reports/quality-gates.json` 和 TopN/CSV/敏感标记/乱码门禁；新增 `scripts/maimai_url.py` 并在 JD delivery 与 AI Infra 外联交付中清洗脉脉 tracking URL。`scripts/jd_talent_delivery_feishu.py` 增加发布前 package 校验、token/raw/db/zip/trackable 扫描、质量门禁读取和 Sheet 回读与本地 CSV 前几行比对；workflow/skill 文档已写明 scorecard-only 前置、argv-list lark-cli、range-limited `sheets +write` 恢复路径。验证：新增 RED 测试先失败后转绿；聚焦套件 `70 passed`；`py_compile` 通过；`git diff --check` 通过；全量 `python -m pytest tests scripts -q` -> `831 passed, 1 warning`，warning 为既有 `scripts/test_boss.py` event loop deprecation。

- 2026-05-23 02 混元大模型数据产品专家/leader JD 人才库推荐：本轮输出目录为 `data/output/02-hunyuan-llm-data-product-lead-2026-05-23/`。已复制 JD 到 `source/jd.md`，基于 `data/campaigns/hunyuan-02-llm-data-product-lead-2026-05-22/strategy.json` 生成岗位画像与 scorecard；推荐报告对齐详情后主库级精排 `data/output/hunyuan-8jd-main-db-match-after-detail-2026-05-23/`，主库候选人 `13332`，分层 `A=2/B=151/C=1724/淘汰=11455`，本地交付 Top30（P0=2/P1=28）。核心产物包括 `profile/role-deep-dive.md`、`profile/role-profile.json`、`scoring/scorecard.json`、`scoring/coarse-screen.json/md`、`scoring/detailed-rank.json/md`、`reports/talent-recommendation.md/json`、`reports/outreach-queue.csv/md`、`feishu/publish-manifest.json`、`feishu/publish-results.json`、`feishu/sheet-outreach-angle-fix.json`。已清理外联 `profile_url` 中的 `trackable_token`，本地生成阶段未触发平台搜索，未写 `match_scores`。
- 2026-05-23 02 混元大模型数据产品专家/leader 飞书发布：已发布到 Wiki space `7642607697183001542` 的父节点 `UCNTwycawitpuckCVB9cskijn8f`（`https://sq8org1v4k6.feishu.cn/wiki/UCNTwycawitpuckCVB9cskijn8f`）。父节点下 4 个子节点：JD `QxoMdeUXioDUO4x3r7ZcuVObnTg` / `F4pTwFkMji2QR3kx61Xcza5cnPc`、role profile `OQfNdZiqgo4cjsx2s7Tc02Pmnbe` / `FJ3UwW67NihopNktwWocEbRyn9d`、recommendation report `DhuJdEu0Mo2Ym7x3n4GcZgMDnzd` / `MVzMwrrMgi6CSCkSypoc1yy0ntb`、outreach queue sheet `Dl7bs3HuEhnyRHtDcFycukjlnjj` / `BHcWwqOAtiUB7ykAJUccdJnsnpg`。直达链接：JD `https://sq8org1v4k6.feishu.cn/docx/QxoMdeUXioDUO4x3r7ZcuVObnTg`，画像 `https://sq8org1v4k6.feishu.cn/docx/OQfNdZiqgo4cjsx2s7Tc02Pmnbe`，推荐报告 `https://sq8org1v4k6.feishu.cn/docx/DhuJdEu0Mo2Ym7x3n4GcZgMDnzd`，外联 Sheet `https://sq8org1v4k6.feishu.cn/sheets/Dl7bs3HuEhnyRHtDcFycukjlnjj`。发布后已用 `sheets +write` 修正外联建议列 `N2:N31` 并读回 `N1:N5`。验证：`wiki +node-list` 返回 4 个子节点，docx outline 读回 3 个，sheet `Z21AQn` 读回 1 个；`python -m pytest tests/test_jd_talent_delivery_feishu.py tests/test_jd_talent_delivery_cli.py tests/test_jd_talent_delivery_workflow.py tests/test_jd_talent_delivery_match.py -q` -> `44 passed`，自定义 JSON/发布结果校验通过，敏感标记扫描无命中，`git diff --check` 通过。`lark-cli doctor` 通过但提示当前 `1.0.36` 可更新到 `1.0.39`。

- 2026-05-23 01 混元大模型数据策略负责人 JD 人才库推荐：本轮输出目录为 `data/output/01-hunyuan-llm-data-strategy-lead-2026-05-23/`。已复制 JD 到 `source/jd.md`，基于 `data/campaigns/hunyuan-01-llm-data-strategy-lead-2026-05-22/strategy.json` 重写岗位画像与 scorecard，并用 `data/talent.db` 只读重新生成粗筛/精排结果。推荐结果：主库候选人 `13332`，分层 `A=2/B=26/C=1213/淘汰=12091`，本地交付 Top30；核心产物包括 `profile/role-deep-dive.md`、`scoring/scorecard.json`、`scoring/coarse-screen.json/md`、`scoring/detailed-rank.json/md`、`reports/talent-recommendation.md/json`、`reports/outreach-queue.csv/md`、`feishu/publish-manifest.json`。校验：必要文件齐全，Top30 JSON 与 30 行外联 CSV 可解析，Feishu manifest 无 DB/zip/raw/sync bundle 敏感路径；本地生成阶段未触发平台搜索，未写 `match_scores`。
- 2026-05-23 01 混元大模型数据策略负责人飞书发布：已发布到 Wiki space `7642607697183001542` 的父节点 `MbEEw5vNUiHUGpk6hWncNlKnnLb`（标题 `混元大模型数据策略负责人`）。父节点下 4 个子节点：JD `QF3odbjReoPJi8xVEuQcEVhfnBh` / `PJ5Ww8dbhiWfhSkGan5c7kzBn3e`、role profile `OHmdddSQ8oLbNSxV9nScfHNDn5g` / `LP0TwUNZxiM93ZkrMAechGcbnfb`、recommendation report `YdpMdLZ4Pos6c6x5dvzcbcaHnjh` / `PKNewgXuNizMo3kE9bhc3pdFnEf`、outreach queue sheet `VCchsoEVchGv5Atg99pcoNhsnvb` / `G3c6wZFgOivx12k3nZ9cWTMnnYf`。本地结果写入 `feishu/publish-results.json` 和 `feishu/dry-run-results.json`；恢复发布时 4 个子节点均为 `reused_existing=true`，未重复导入。验证：`wiki +node-list` 返回 4 个子节点，docx outline 读回 3 个，sheet `OVWwfA` 读回 1 个；`python -m pytest tests/test_jd_talent_delivery_feishu.py tests/test_jd_talent_delivery_cli.py -q` -> `31 passed`，`git diff --check` 通过。未上传 DB/zip/raw/sync bundle，未写 `match_scores`。
- 2026-05-23 JD Talent Delivery Task 2：新增 runtime-neutral canonical workflow `agents/workflows/jd-talent-delivery/AGENT.md`，覆盖资源索引、S0-S7、scorecard 一致性、安全边界和飞书停机条件；新增 `tests/test_jd_talent_delivery_workflow.py` 并将 `jd-talent-delivery` 加入架构 `WORKFLOWS`。由于架构测试要求每个 workflow 都有运行时 adapter，新增最小 `.claude/skills/jd-talent-delivery/SKILL.md` 指向 canonical workflow。验证：先跑 `python -m pytest tests/test_jd_talent_delivery_workflow.py -q` 红灯，因缺少 workflow 文件 `FileNotFoundError` 失败；创建 workflow 后同命令 `4 passed`；新增架构列表后组合测试因缺少 adapter 失败；补 adapter 后 `python -m pytest tests/test_jd_talent_delivery_workflow.py tests/test_agent_architecture.py -q` -> `9 passed`。`git diff --check` 通过；workflow 私有运行时禁词扫描无命中。
- 2026-05-23 详情后主库级重新精排：已用 `python -m scripts.maimai_campaign_rank --mode detailed --limit 13332` 对 8 个混元 JD 全量重跑，输出目录为 `data/output/hunyuan-8jd-main-db-match-after-detail-2026-05-23/`。汇总见 `main-db-detailed-rank-after-detail-summary.md/json`，前后对比见 `main-db-detailed-rank-pre-post-comparison.md/json`。与详情写入前同口径相比，8JD 合计 `A 16->19 (+3)`、`B 450->493 (+43)`、`C 9686->10036 (+350)`、`A+B 466->512 (+46)`、`A+B+C 10152->10548 (+396)`、`淘汰 96504->96108 (-396)`。验证：3 个汇总 JSON 均可解析，8 个 rank JSON 均为 `total_candidates=13332`，8 个 Markdown 输出存在，主库 `PRAGMA integrity_check=ok/candidates=13332/candidate_details=13332/source_profiles=13332/maimai_detail_capture_rows=3625`。
- 2026-05-23 ABC 详情写入主库：写入前备份为 `data/backups/talent-main-before-hunyuan-abc-detail-apply-20260523-003549.db`，备份 `integrity=ok/candidates=13332/source_profiles=13332/candidate_details=13332/maimai_detail_capture=977`。已修正专用 detail campaign manifest 缺少 `schema=maimai_ai_infra_v2_campaign` 导致 pipeline apply 前置校验失败的问题；失败发生在写库前，随后从 `detail-abc-pack-001` 重新顺序 apply。27 个 pack 全部写入主库，汇总 `matched=2648/written=2648/unmatched=0/failed_jobs=0/capture_blockers=0/apply_blockers=0`。写入后主库 `integrity=ok/candidates=13332/source_profiles=13332/candidate_details=13332/maimai_detail_capture=3625/hunyuan_abc_capture_rows=2648/detailed_candidates=13319`。摘要见 `data/output/hunyuan-8jd-abc-detail-main-apply-2026-05-23/main-detail-apply-summary.md/json`，逐包 JSONL 为 `apply-summary.jsonl`。
- 2026-05-22 ABC 详情抓取启动：新增 `scripts/hunyuan_abc_detail_tasks.py`，从 `data/output/hunyuan-8jd-main-db-match-2026-05-22/main-db-detailed-rank-summary.json` 读取 8JD A/B/C 三档，生成 `data/campaigns/hunyuan-8jd-abc-detail-2026-05-22/`。ABC 输入行 `10152`，去重候选人 `3173`，已有 `maimai_detail_capture` 跳过 `525`，缺失 `0`，可执行目标 `2648`，拆为 `27` 个 pack（前 26 个 100 人，最后 48 人）。CDP 健康检查通过：`hasLoginPrompt=false/hasCaptcha=false/hasTalentBank=true`。后台无人值守 runner 已启动，PID `19304`，主库 apply 策略为 `manual_only`。
- 2026-05-22 ABC 详情并发试跑：`scripts/hunyuan_abc_detail_tasks.py` 已支持 `--pack-ids` 与 `--runner-id`，避免多进程抢同一 pack；原顺序 PID `19304` 在 `pack002=32/100` 时停止，随后分片试跑 2 -> 3 -> 4 并发。4 并发截至 `22:54:04` 进度 `709/2648`，`pack001` 到 `pack005` 已完成，`pack006=82/100`、`pack007=62/100`、`pack008=43/100`、`pack009=22/100`；各分片 stderr 均为 `0`，未见平台阻断。验证：`python -m py_compile scripts/hunyuan_abc_detail_tasks.py` 通过；`python -m pytest tests/test_maimai_ai_infra_detail_live_gate.py tests/test_maimai_detail_import.py -q` -> `24 passed`。
- 2026-05-22 ABC 详情并发补位：新增 `scripts/hunyuan_abc_parallel_supervisor.ps1`，自动识别完成/活动 pack 并保持最多 4 个分片。已修正 supervisor 不应把自身 process json 算作 worker 的监控口径。当前 supervisor PID `27972`，状态文件 `data/campaigns/hunyuan-8jd-abc-detail-2026-05-22/state/parallel-supervisor-state.json` 显示 `completed_packs=8/27`、`done_jobs=931/2648`、`percent=35.16`，活动分片为 `pack009/010/011/012`，stderr 均为 `0`。
- 2026-05-23 ABC 详情抓取完成：`parallel-supervisor-state.json` 显示 `status=completed`、`completed_packs=27/27`、`done_jobs=2648/2648`、`percent=100`，完成时间 `2026-05-23T00:29:08`。27 个 dry-run 报告全部存在，汇总 `matched=2648/unmatched=0/failed_jobs=0/capture_blockers=0/apply_blockers=0`，没有 dirty 包；所有 stderr 日志为空。未自动 apply `data/talent.db`。
- 2026-05-22 主库真实同步：报告为 `data/output/hunyuan-8jd-main-sync-apply-2026-05-22/main-sync-apply-summary-20260522-211400.md/json`；同步前备份为 `data/backups/talent-main-before-hunyuan-8jd-sync-20260522-211400.db`，备份 `candidates=5497/source_profiles=5497/candidate_details=5497/sync_imports=2/integrity=ok`。8 个 bundle 顺序 apply 后主库 `candidates=13332/source_profiles=13332/candidate_details=13332/pending_merges=0/sync_conflicts=1814/sync_imports=10`，`PRAGMA integrity_check=ok`。候选人级 apply 合计 `created=7835/merged=1722/conflicts=14/skipped=0`。
- 2026-05-22 主库级逐 JD detailed rank：输出目录为 `data/output/hunyuan-8jd-main-db-match-2026-05-22/`，8 个 JD 均生成 `*-main-db-detailed-rank.md/json` 和 `main-db-detailed-rank-summary.md/json`。A/B/C 数：01=`1/19/1182`，02=`2/146/1679`，03=`0/0/931`，04=`0/1/997`，05=`7/236/1615`，06=`0/1/1141`，07=`0/5/974`，08=`6/42/1167`。03/04 因 JD 正文缺失仍为低置信。
- 2026-05-22 主库同步预检：输出目录为 `data/output/hunyuan-8jd-main-sync-precheck-2026-05-22/`，包含 8 个 campaign bundle 与 `main-sync-dry-run-summary.md/json`。8 个 bundle 均 `verify_ok=true`；逐 bundle dry-run 合计 `exported=9557/created=9392/merged=165/conflicts=0/skipped=0`。`data/talent.db` 未 apply；SQLite 读/备份预检使文件 mtime 变为 `2026-05-22T20:37:21`，但业务计数仍为 `candidates=5497/source_profiles=5497/candidate_details=5497/sync_imports=2`，最新 `sync_imports.imported_at=2026-05-20 04:12:30`，`PRAGMA integrity_check=ok`。
- 测试库累计 apply 模拟曾启动但因耗时过长中止，临时 `main-sync-simulation-*.db*` 已清理；该模拟不作为证据。真实写入前应即时备份主库，再顺序 apply 8 个 bundle 并做 `PRAGMA integrity_check`、候选人数、sync_conflicts 验证。
- 2026-05-22 继续执行补充四：04 人工刷新搜索模板后已补齐 `search-wave-001` 剩余 9 页；标准化后 30/30 页齐备，dry-run/apply `raw=516/unique=516/created=516/pending=0/errors=0`；04 Campaign DB `candidates=516/source_profiles=516/candidate_details=516/pending_merges=0/sync_conflicts=0`，`PRAGMA integrity_check=ok`，list rank 为 `A=0/B=0/C=27/淘汰=473`。
- 混元 8JD 首轮 campaign-local 扩库完成：01/02/03/04/05/06/07/08 Campaign DB 当前分别为 `2662/1079/734/516/1889/907/937/833` 人；均已完成 list rank，且主库 `data/talent.db` 未写。
- 验证：聚焦回归 `python -m pytest tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_campaign_search_plan.py tests/test_maimai_campaign_orchestrator.py -q` -> `58 passed`；全量 `python -m pytest tests scripts -q` -> `765 passed, 1 warning`，warning 为既有 `scripts/test_boss.py` event loop deprecation。
- 2026-05-22 继续执行补充三：03 验证码恢复后已补齐 `search-wave-001` 剩余 28 页；标准化后 30/30 页齐备，dry-run/apply `raw=734/unique=734/created=734/pending=0/errors=0`；03 Campaign DB `candidates=734/source_profiles=734/candidate_details=734/pending_merges=0/sync_conflicts=0`，`PRAGMA integrity_check=ok`，list rank 为 `A=0/B=0/C=71/淘汰=429`。
- 04 岗位 `search-wave-001` 在 `unit-000005 page 2` 触发 `http_432`，按 workflow 停机；已标准化成功 21/30 页作为 checkpoint，但未对 04 执行 dry-run/apply。已写 `reports/interruption-search-wave-001-2026-05-22.json`、`state/continuation-plan.json` 和 `state/search-wave-001-resume-after-http-432-plan.json`，剩余 9 页等待人工处理风控/安全提示后恢复。
- 04 恢复尝试在预检阶段返回 `missing_search_template`：页面健康检查显示仍在人才银行页、无登录弹窗/验证码，但 `templateStatus.hasSearchTemplate=false`，因此没有进入任何 batch，也没有新增 raw page。已写 `reports/interruption-search-wave-001-missing-template-2026-05-22.json`，下一步需在人才银行页手动执行一次搜索刷新模板后再恢复。
- 2026-05-22 继续执行补充二：08 验证码恢复后已补齐 `search-wave-001` 剩余 7 页，并完成 `search-wave-002` 10 页；08 Campaign DB 最终 `candidates=833/source_profiles=833/candidate_details=833/pending_merges=0/sync_conflicts=0`，`PRAGMA integrity_check=ok`，list rank 为 `A=0/B=3/C=61/淘汰=769`。
- 06 岗位首轮 45 页完成：`search-wave-001` dry-run/apply `raw=907/created=907/pending=0/errors=0`；06 Campaign DB `candidates=907/pending_merges=0/sync_conflicts=0`，`PRAGMA integrity_check=ok`，list rank 为 `A=0/B=0/C=62/淘汰=845`。
- 07 岗位首轮 45 页完成：`search-wave-001` dry-run/apply `raw=937/created=937/pending=0/errors=0`；07 Campaign DB `candidates=937/pending_merges=0/sync_conflicts=0`，`PRAGMA integrity_check=ok`，list rank 为 `A=0/B=1/C=74/淘汰=862`。
- 02 岗位首轮 40 页完成：`search-wave-001` dry-run/apply `raw=1079/created=1079/pending=0/errors=0`；02 Campaign DB `candidates=1079/pending_merges=0/sync_conflicts=0`，`PRAGMA integrity_check=ok`，list rank 为 `A=0/B=38/C=99/淘汰=942`。
- 03 岗位 `search-wave-001` 在 `unit-000001 page 3` 触发 `captcha_api`，按 workflow 停机；已标准化成功 2/30 页作为 checkpoint，但未对 03 执行 dry-run/apply。已写 `reports/interruption-search-wave-001-2026-05-22.json`、`state/continuation-plan.json` 和 `state/search-wave-001-resume-after-captcha-plan.json`，剩余 28 页等待人工处理验证码后恢复。
- 2026-05-22 继续执行补充：01 岗位验证码恢复后已补齐 `search-wave-003` 剩余 6 页，第三波 dry-run `raw=991/unique=991/created=678/merged=313/pending=0/errors=0` 并 apply clean；01 Campaign DB 最终 `candidates=2662/source_profiles=2662/candidate_details=2662/pending_merges=0/sync_conflicts=0`，`PRAGMA integrity_check=ok`。
- 05 岗位首轮 100 页完成：`search-wave-001` dry-run/apply `raw=907/created=907/pending=0/errors=0`；`search-wave-002` dry-run/apply `raw=986/created=982/merged=4/pending=0/errors=0`；05 Campaign DB 最终 `candidates=1889/source_profiles=1889/candidate_details=1889/pending_merges=0/sync_conflicts=0`，`PRAGMA integrity_check=ok`，list rank 为 `A=0/B=3/C=154/淘汰=1732`。
- 08 岗位 `search-wave-001` 在 `unit-000009 page 4` 触发 `captcha_api`，按 workflow 停机；已标准化成功 43/50 页作为 checkpoint，但未对 08 执行 dry-run/apply。已写 `reports/interruption-search-wave-001-2026-05-22.json`、`state/continuation-plan.json` 和 `state/search-wave-001-resume-after-captcha-plan.json`，剩余 7 页等待人工处理验证码后恢复。
- 2026-05-22 继续执行结果：`scripts/maimai_ai_infra_pipeline.py` 已支持 generic JD `strategy.json`，`run-campaign` 不再因缺少 legacy AI Infra keys 阻塞；新增回归 `test_run_campaign_wave_generates_plan_files_for_generic_jd_strategy`，聚焦测试 `python -m pytest tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_campaign_search_plan.py tests/test_maimai_campaign_orchestrator.py -q` -> `58 passed`。
- 01 岗位 `search-wave-001`：live run `status=completed/stopReason=null/batches=10/contacts=1355`；标准化 50 页；dry-run `raw=984/unique=984/created=984/merged=0/pending=0/errors=0`；Campaign DB apply clean。
- 01 岗位 `search-wave-002`：live run `status=completed/stopReason=null/batches=10/contacts=1367`；标准化 50 页；dry-run `raw=1282/unique=1282/created=1000/merged=282/pending=0/errors=0`；Campaign DB apply clean。
- 01 Campaign DB 当前状态：`candidates=1984/source_profiles=1984/candidate_details=1984/pending_merges=0/sync_conflicts=0`，`PRAGMA integrity_check=ok`；主库 `data/talent.db` 未写。
- 01 岗位当前 list rank：`reports/list-rank.md/json` 已生成，列表证据下 `A=0/B=0/C=61/淘汰=923`，说明仍需完成剩余搜索与后续详情抓取后再做高精度结论。
- 01 岗位 `search-wave-003`：live run 在 `unit-000029 page 5` 触发 `captcha_api`，按 workflow 停机；已标准化成功的 44/50 页作为 checkpoint，但未对第三波执行 dry-run/apply。已写 `reports/interruption-search-wave-003-2026-05-22.json`、`state/continuation-plan.json` 和 `state/search-wave-003-resume-after-captcha-plan.json`，剩余 6 页等待人工处理验证码后恢复。
- 2026-05-22：已执行混元 8JD batch campaign 合同生成与离线搜索计划编译；产物根目录为 `data/campaigns/hunyuan-ai-data-8jd-batch-2026-05-22/`，8 个 JD 独立 campaign root 均已生成。
- 8 个 campaign 首轮总计划页数为 500：01=150、02=40、03=30、04=30、05=100、06=45、07=45、08=60；对应 wave 数为 3/1/1/1/2/1/1/2。
- 关键产物：batch `campaign-manifest.json`、`jd-index.json`、`reports/batch-search-plan-summary.md/json`；每个 JD 的 `requirements.json`、`strategy.json`、`run-policy.json`、`campaign-manifest.json`、`search-implementation-plan.md`、`search-plan.json`、`search-units.jsonl`、`state/search-wave-plan.json`。
- 校验：8 个 campaign workflow status 可读；全部 search units 满足 `allcompanies=""`、`positions=""`、`query_relation=0`；03/04 `missing_fields` 已包含 `岗位职责正文`、`任职要求正文`、`技术栈细节`；样板词扫描无命中；生成器 `py_compile` 通过；聚焦测试 `python -m pytest tests/test_maimai_campaign_search_plan.py tests/test_maimai_campaign_orchestrator.py tests/test_maimai_search_filter_clearing.py -q` -> `35 passed`。
- 兼容修正：新 campaign 的 `campaign-manifest.json.schema` 写为 pipeline 兼容的 `maimai_ai_infra_v2_campaign`，同时用 `contract_schema=maimai_jd_campaign_v2` 标识 JD 合同类型，避免后续标准化/Campaign DB pipeline 因 schema 不兼容阻塞。
- 本轮未执行真实脉脉搜索，未写 Campaign DB，未写主库 `data/talent.db`；下一步必须等待用户确认 batch 搜索计划。
- 用户确认 batch 搜索计划后，已更新 8 个 campaign 的 `run-policy.json` 和 `state/stage-state.json`，并启动 CDP 浏览器；session manifest 写入 `data/campaigns/hunyuan-ai-data-8jd-batch-2026-05-22/state/browser-bootstrap.json`。
- CDP 预检：启动前 `http://127.0.0.1:9888/json/version` 不可用；启动后返回 Chrome CDP version 信息，说明端口可用。当前状态为 `browser_bootstrap_launched_waiting_manual_handoff`。
- 当前仍未执行真实脉脉搜索，未写 Campaign DB，未写主库 `data/talent.db`；下一步需要人工在该浏览器内登录脉脉、进入人才银行页并手动执行一次搜索模板。
- 2026-05-22：已阅读 `docs/business-requirements/` 下 8 个文件名含 `hunyuan` 的 JD，并生成综合扩库型脉脉寻访计划：`docs/superpowers/plans/2026-05-22-hunyuan-8jd-maimai-sourcing-plan.md`。
- 本计划采用“1 个 batch 计划 + 8 个 JD campaign root”的结构，先用共享公司池/关键词簇扩充 Campaign DB 与本地人才库，再用每个 JD 的 `strategy.json` 对 `data/talent.db` 做独立精排。
- 已明确首轮 500 页预算分配、6 类人才画像簇、query-only 搜索边界、排除规则、详情抓取规则、Campaign DB 到主库的人工同步边界和逐 JD 本地精排命令形态。
- 03/04 两个 JD 正文为“待补充”，计划中已标为低置信度；后续不能用它们给强结论，精排前需补正式 JD 或通过交付反馈校准。
- 校验：计划文档样板词扫描无命中；`git diff --check -- docs/superpowers/plans/2026-05-22-hunyuan-8jd-maimai-sourcing-plan.md tasks/todo.md` 通过。
- 本轮未执行真实脉脉搜索，未写 Campaign DB，未写主库 `data/talent.db`。
- 本轮调查中，重点区分“搜索执行真实使用的计划”和“后续评分/交付复用的通用脚本 schema”，避免把 AI Infra 样板残留误判成单点文案错误。
- 本轮完成解释性核查和实施计划设计，未改 `data/campaigns/hunyuan-data-strategy-lead-2026-05-21/` 计划文件，也未运行全量 pytest。
- 关键发现：`search-units.jsonl`、`state/search-wave-*.json`、`state/live-search-wave-*.json` 是混元岗位实际搜索计划；根目录 `search-plan.json` 和最终报告标题/方向仍带有 AI Infra V2 痕迹，应作为后续调整的高优先级复核点。
- 进一步证据：严格 `allcompanies/positions` smoke 返回 0 人，query-only company anchor 返回 30 人，因此放弃严格结构化过滤有依据；但 wave002 resume 的真实请求出现 `allcompanies=BAT` 残留，说明 query-only 计划仍需显式清空高风险结构化过滤字段。
- 提案方向：将 `maimai_ai_infra_*` 搜索计划、评分、方向覆盖、交付报告脚本拆为 campaign-generic runtime + role-specific strategy；新增公司/产品线 alias registry 与交付评价 feedback contract，让下次 JD campaign 能动态生成公司映射、评分维度和下一轮搜索策略。
- 已将实施计划写入 `docs/superpowers/plans/2026-05-22-maimai-jd-campaign-generalization.md`，按 8 个工程任务拆分：先修 query-only 模板过滤残留，再补公司/产品线 registry、通用 search-plan 编译、通用 ranking、通用交付报告、feedback contract、混元 guardrail fixture/test 和最终回归。
- 本计划阶段不执行真实脉脉搜索、不修改历史 campaign raw、不写 `data/talent.db`；后续实现必须先跑聚焦测试，再跑相关回归与 `git diff --check`。
- `tasks/todo.md` 已缩减为当前工作台；完整历史迁移到 `tasks/archive/2026-05.md`。
- 迁移前：`2621` lines，`364242` bytes；迁移后：`18` lines，`1503` bytes。
- 归档检索验证通过：`rg -n "飞书推送|LLM 推理|GitHub HR|工作台提示" tasks/archive/2026-05.md` 命中历史记录。
- diff hygiene 通过：`git diff --check -- tasks/todo.md tasks/archive/README.md tasks/archive/2026-05.md AGENTS.md`。
- 本轮只改文档/任务账本，未运行全量 pytest；若后续改到脚本或 workflow，再运行 `python -m pytest tests scripts -q`。
- 已实现 JD-driven Maimai campaign 通用化第一阶段：query-only 默认清空 `allcompanies/positions` 和地域高风险模板残留；新增公司/产品线 registry；新增通用 search-plan、rank、delivery report、feedback contract；orchestrator 对 JD-style strategy 路由到 generic modules，对 legacy AI Infra strategy 保持兼容。
- 新增混元 guardrail fixture/test，锁定混元 strategy 生成链路不得出现 `AI Infra`、`训练框架`、`推理引擎` 样板残留，并确认 query-only `allcompanies=""`。
- Skill/workflow 已补 `company_product_mappings`、`delivery_feedback_contract` 和 S14 交付反馈阶段，要求用户评价落为机器可读 `feedback/*.json` 再生成下一轮 `strategy-adjustment*.json`。
- 验证：聚焦回归 `83 passed`；全量 `python -m pytest tests scripts -q` -> `763 passed, 1 warning`；新增/修改脚本 `py_compile` 通过；`git diff --check` 通过。
- 本轮未执行真实脉脉搜索，未修改历史 campaign raw，未写主库 `data/talent.db`。全量 warning 为既有 `scripts/test_boss.py` event loop deprecation，与本次改造无关。
- 已基于 `docs/business-requirements/01-hunyuan-llm-data-strategy-lead.md` 生成 v2 campaign：`data/campaigns/hunyuan-llm-data-strategy-lead-v2-2026-05-22/`。产物包含 `requirements.json`、`strategy.json`、`run-policy.json`、`campaign-manifest.json`、`search-implementation-plan.md`、`search-plan.json`、`search-units.jsonl`、`state/search-wave-plan.json`、`reports/search-plan-summary.md`。
- v2 搜索计划规模：90 个 search units，342 页，拆为 7 个 wave，页数为 `50/50/50/48/48/48/48`；全部 unit 均为 query-only，`allcompanies=""`、`positions=""`，无 `AI Infra/训练框架/推理引擎` 样板残留。
- 本轮 workflow status 通过，聚焦测试 `python -m pytest tests/test_maimai_campaign_search_plan.py tests/test_maimai_campaign_orchestrator.py tests/test_maimai_search_filter_clearing.py -q` -> `35 passed`。尚未执行真实脉脉搜索，等待搜索计划确认。
- 接手后复核：`maimai_campaign_orchestrator status` 仍停在 `draft_pending_search_plan_confirmation`；再次校验 search units 和聚焦测试，确认 `35 passed`，真实脉脉搜索仍未执行。
