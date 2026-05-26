# 本地人才库重构设计

> **日期**: 2026-05-08
> **状态**: Draft
> **背景**: 脉脉 Chrome 插件批量抓取数据后，现有 JSON 文件存储无法支撑大量数据的检索和管理需求

---

## 1. 目标

构建一个本地 SQLite 人才库，支持：
- 1-10 万候选人数据的高效存储与检索
- 三级数据分级（线索级/核心级/详细级）
- 综合评分 + JD 匹配评分双评分体系
- 跨平台去重（脉脉、Boss 等）
- FTS5 全文搜索 + sqlite-vec 向量相似搜索
- 纯数据层设计，不包含评分计算和匹配业务逻辑

## 2. 架构

```
┌─────────────────────────────────────────────────────┐
│  业务层 (已有/计划中)                                │
│  coarse_screener.py  llm_ranker.py  jd_analyzer.py  │
│  score_candidates.py  report_generator.py            │
├─────────────────────────────────────────────────────┤
│  数据访问层 (本次实现)                               │
│  talent_db.py — 统一查询接口                        │
├─────────────────────────────────────────────────────┤
│  存储层 (本次实现)                                   │
│  SQLite: data/talent.db                              │
│  ├─ candidates (结构化字段)                          │
│  ├─ candidate_details (详情 JSON)                    │
│  ├─ candidate_fts (FTS5 全文索引)                    │
│  ├─ candidate_vectors (sqlite-vec 向量)              │
│  ├─ source_profiles (各平台原始数据)                  │
│  ├─ scores + score_events (评分与日志)               │
│  ├─ match_scores (JD 匹配评分)                       │
│  ├─ merge_log + pending_merges (去重)                │
│  └─ company_aliases (公司别名)                       │
└─────────────────────────────────────────────────────┘
```

**核心原则**: 人才库只提供数据读写和查询能力，不参与评分计算和匹配逻辑。业务模块通过 `talent_db.py` 的 API 获取数据，评分结果写回数据库。

## 3. 数据分级策略

| 级别 | 字段范围 | 来源 |
|------|---------|------|
| 线索级 (lead) | name, current_company, current_title, city, source_ids | 搜索结果列表、插件批量导出 |
| 核心级 (core) | + skills, education, work_years, expected_salary, hunting_status | 搜索结果中的结构化数据 |
| 详细级 (detailed) | + work_experience[], education_experience[], project_experience[], raw_data | 详情页抓取、API 完整返回 |

入库时根据数据完整度自动判定级别：
- 仅有 name+company+title → `lead`
- 有 skills+education+work_years → `core`
- 有完整工作经历 → `detailed`

## 4. 表结构

### 4.1 candidates — 主表

```sql
CREATE TABLE candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    gender TEXT,
    age INTEGER,
    city TEXT,
    work_years INTEGER,
    education TEXT,
    current_company TEXT,
    current_title TEXT,
    expected_salary TEXT,
    expected_city TEXT,
    expected_title TEXT,
    hunting_status TEXT,
    skill_tags TEXT,                -- JSON array
    data_level TEXT DEFAULT 'lead', -- lead/core/detailed
    overall_score REAL DEFAULT 0,
    score_version INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(name, current_company, current_title,
           COALESCE(city, ''), COALESCE(education, ''))
);
```

> **注意**: SQLite 中 `NULL != NULL`，`UNIQUE` 约束含 nullable 列时无法正确去重。使用 `COALESCE` 将 NULL 转为空字符串参与唯一性判断。主去重逻辑在 `ingest()` 方法中以程序化方式实现，此约束仅作数据库层兜底。

### 4.2 candidate_details — 详情表

```sql
CREATE TABLE candidate_details (
    candidate_id INTEGER PRIMARY KEY REFERENCES candidates(id) ON DELETE CASCADE,
    work_experience TEXT,          -- JSON array
    education_experience TEXT,     -- JSON array
    project_experience TEXT,       -- JSON array
    raw_data TEXT,                 -- 原始抓取数据 JSON
    summary TEXT                   -- LLM 生成的候选人摘要
);
```

### 4.3 source_profiles — 来源追踪

```sql
CREATE TABLE source_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,        -- maimai/boss/linkedin
    platform_id TEXT,              -- 平台方 user ID
    profile_url TEXT,
    raw_profile TEXT,              -- 该平台的原始数据 JSON
    fetched_at TEXT,
    UNIQUE(platform, platform_id)
);
```

### 4.4 评分相关

#### 综合评分（候选人本身质量）

```sql
-- candidates 表上的 overall_score 字段 + score_events 日志
CREATE TABLE score_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
    old_score REAL,
    new_score REAL,
    trigger_type TEXT NOT NULL,    -- profile_enriched/platform_merged/
                                    -- career_updated/manual_evaluation/
                                    -- decay_adjustment
    trigger_detail TEXT,           -- JSON: 具体变更内容
    computed_at TEXT DEFAULT (datetime('now'))
);
```

综合评分特点：
- 反映候选人本身质量，与具体 JD 无关
- 随信息更新、数据合并、履历变化、人工评价等事件更新
- 类似信用分，信息越丰富分数越准确
- 更新时记录变动日志（score_events）

#### JD 匹配评分（候选人对特定 JD 的匹配度）

```sql
CREATE TABLE match_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
    jd_id TEXT NOT NULL,
    match_type TEXT NOT NULL,      -- coarse/llm_rank/calibration/final
    score REAL,
    dimensions TEXT,               -- JSON: {"岗位匹配度":85, "技能覆盖率":72, ...}
    reason TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(candidate_id, jd_id, match_type)
);
```

匹配评分特点：
- 同一候选人，不同 JD 得分不同
- 综合评分影响匹配基准，但主要由 JD 需求决定
- 由 Pipeline 业务层计算，人才库只存储和查询

#### 两者的关系

综合评分（候选人质量）作为匹配评分的参考基准。综合分高的候选人，在技能匹配的前提下匹配分通常也高。但匹配分主要由 JD 的具体需求决定。

### 4.5 去重相关

```sql
-- 公司别名表
CREATE TABLE company_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL,
    alias TEXT NOT NULL,
    UNIQUE(canonical_name, alias)
);

-- 合并日志
CREATE TABLE merge_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    survivor_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
    merged_id INTEGER,
    match_type TEXT,               -- exact/alias/manual
    merged_fields TEXT,            -- JSON
    merged_at TEXT DEFAULT (datetime('now'))
);

-- 待确认的合并候选
CREATE TABLE pending_merges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    existing_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
    new_data TEXT NOT NULL,        -- JSON
    match_fields TEXT,             -- JSON: 哪些字段匹配了
    status TEXT DEFAULT 'pending', -- pending/approved/rejected
    created_at TEXT DEFAULT (datetime('now')),
    resolved_at TEXT,
    resolved_by TEXT
);
```

### 4.6 索引

```sql
CREATE INDEX idx_candidates_company ON candidates(current_company);
CREATE INDEX idx_candidates_title ON candidates(current_title);
CREATE INDEX idx_candidates_city ON candidates(city);
CREATE INDEX idx_candidates_education ON candidates(education);
CREATE INDEX idx_candidates_work_years ON candidates(work_years);
CREATE INDEX idx_candidates_data_level ON candidates(data_level);
CREATE INDEX idx_candidates_score ON candidates(overall_score DESC);
CREATE INDEX idx_source_platform ON source_profiles(platform);
CREATE INDEX idx_source_candidate ON source_profiles(candidate_id);
CREATE INDEX idx_match_scores_jd ON match_scores(jd_id);
CREATE INDEX idx_match_scores_candidate_jd ON match_scores(candidate_id, jd_id);
CREATE INDEX idx_score_events_candidate ON score_events(candidate_id);
```

### 4.7 FTS5 全文索引

```sql
CREATE VIRTUAL TABLE candidate_fts USING fts5(
    name, company, title, skills, education, city,
    content='candidates',
    content_rowid='id'
);

-- FTS5 外部内容表必须通过触发器保持同步
-- FTS 列映射: company → candidates.current_company, title → candidates.current_title,
--             skills → candidates.skill_tags

CREATE TRIGGER candidates_ai AFTER INSERT ON candidates BEGIN
    INSERT INTO candidate_fts(rowid, name, company, title, skills, education, city)
    VALUES (new.id, new.name, new.current_company, new.current_title,
            new.skill_tags, new.education, new.city);
END;

CREATE TRIGGER candidates_ad AFTER DELETE ON candidates BEGIN
    INSERT INTO candidate_fts(candidate_fts, rowid, name, company, title, skills, education, city)
    VALUES ('delete', old.id, old.name, old.current_company, old.current_title,
            old.skill_tags, old.education, old.city);
END;

CREATE TRIGGER candidates_au AFTER UPDATE ON candidates BEGIN
    INSERT INTO candidate_fts(candidate_fts, rowid, name, company, title, skills, education, city)
    VALUES ('delete', old.id, old.name, old.current_company, old.current_title,
            old.skill_tags, old.education, old.city);
    INSERT INTO candidate_fts(rowid, name, company, title, skills, education, city)
    VALUES (new.id, new.name, new.current_company, new.current_title,
            new.skill_tags, new.education, new.city);
END;
```

### 4.8 向量索引（sqlite-vec）

```sql
CREATE VIRTUAL TABLE candidate_vectors USING vec0(
    candidate_id INTEGER PRIMARY KEY,
    embedding float[384]
);
```

向量生成职责在业务层：
1. 入库完成后，业务层异步取候选人文本
2. 用 sentence-transformers (all-MiniLM-L6-v2) 生成 384 维向量
3. 调用 `db.save_embedding()` 存储
4. 向量搜索时 talent_db 直接查 sqlite-vec

人才库不依赖 embedding 模型。

## 5. 去重策略

### 去重判定规则

| 级别 | 匹配条件 | 处理方式 |
|------|---------|---------|
| 完全匹配 | 姓名 + 当前公司 + 当前职位 + 城市 + 学历 | 自动合并 |
| 疑似重复 | 姓名 + 公司别名匹配，或其他字段部分匹配 | 写入 pending_merges，人工确认 |
| 新记录 | 无匹配 | 新建候选人记录 |

### 合并策略

| 字段 | 规则 |
|------|------|
| 结构化字段 | 取信息更完整的来源；冲突时取最新的 |
| skill_tags | 并集合并 |
| 工作经历 | 按 (公司+时间段) 去重后合并 |
| 详情数据 | 各平台原始数据独立保存在 source_profiles，不覆盖 |
| 综合评分 | 合并后触发重新计算（由业务层决定） |

## 6. 查询 API（talent_db.py）

### 接口定义

```python
class TalentDB:
    def __init__(self, db_path: Path)
    def close(self)

    # ── 入库与去重 ──
    def ingest(self, candidate_data: dict, platform: str) -> int
    def resolve_merge(self, pending_id: int, action: str) -> None
    def batch_ingest(self, candidates: list[dict], platform: str) -> IngestResult

    # ── 数据更新 ──
    def enrich(self, candidate_id: int, detail_data: dict) -> None
    def update_overall_score(self, candidate_id: int, score: float,
                             trigger: str, detail: dict = None) -> None
    def save_match_score(self, candidate_id: int, jd_id: str,
                         match_type: str, score: float,
                         dimensions: dict = None, reason: str = None) -> None

    # ── 查询：ID / 条件 ──
    def get(self, candidate_id: int) -> Candidate | None
    def get_detail(self, candidate_id: int) -> CandidateDetail | None
    def get_sources(self, candidate_id: int) -> list[SourceProfile]
    def search(self, filters: CandidateFilter,
               sort: SortSpec = None,
               page: int = 1, page_size: int = 50) -> PageResult

    # ── 查询：全文搜索 ──
    def fulltext_search(self, query: str, limit: int = 50) -> list[SearchHit]

    # ── 查询：向量相似 ──
    def vector_search(self, query_vector: bytes, limit: int = 20) -> list[VectorHit]
        # 接受预计算的向量（由业务层生成），不依赖 embedding 模型
    def save_embedding(self, candidate_id: int, embedding: bytes) -> None

    # ── 查询：JD 匹配相关 ──
    def get_match_scores(self, jd_id: str,
                         match_type: str = None) -> list[MatchScore]
    def get_top_candidates(self, jd_id: str, top_n: int = 10) -> list[Candidate]

    # ── 统计 ──
    def count(self, filters: CandidateFilter = None) -> int
    def pending_merges(self) -> list[PendingMerge]
```

### 过滤与排序

```python
@dataclass
class CandidateFilter:
    companies: list[str] = None
    titles: list[str] = None
    cities: list[str] = None
    education_levels: list[str] = None
    min_work_years: int = None
    max_work_years: int = None
    skills_any: list[str] = None       # 包含任一，用 json_each + IN 子查询
    skills_all: list[str] = None       # 包含全部，用 json_each + GROUP BY HAVING
    data_level: str = None
    hunting_status: list[str] = None
    min_score: float = None
    max_score: float = None
    platforms: list[str] = None        # JOIN source_profiles 过滤
    updated_after: str = None

@dataclass
class SortSpec:
    field: str          # overall_score / updated_at / work_years / ...
    direction: str = "desc"

@dataclass
class PageResult:
    items: list[Candidate]
    total: int
    page: int
    page_size: int
```

### 返回类型定义

```python
@dataclass
class Candidate:
    id: int
    name: str
    gender: str | None
    age: int | None
    city: str | None
    work_years: int | None
    education: str | None
    current_company: str | None
    current_title: str | None
    expected_salary: str | None
    expected_city: str | None
    expected_title: str | None
    hunting_status: str | None
    skill_tags: list[str]       # 解析后的列表
    data_level: str
    overall_score: float
    score_version: int
    created_at: str
    updated_at: str

@dataclass
class CandidateDetail:
    candidate_id: int
    work_experience: list[dict] | None
    education_experience: list[dict] | None
    project_experience: list[dict] | None
    raw_data: dict | None
    summary: str | None

@dataclass
class SourceProfile:
    id: int
    candidate_id: int
    platform: str
    platform_id: str | None
    profile_url: str | None
    raw_profile: dict | None
    fetched_at: str | None

@dataclass
class SearchHit:
    id: int
    rank: float          # FTS5 match score
    snippet: str         # 高亮摘要

@dataclass
class VectorHit:
    id: int
    similarity: float    # cosine distance
    name: str
    current_company: str | None
    current_title: str | None

@dataclass
class MatchScore:
    id: int
    candidate_id: int
    jd_id: str
    match_type: str
    score: float
    dimensions: dict | None
    reason: str | None
    created_at: str

@dataclass
class PendingMerge:
    id: int
    existing_id: int
    new_data: dict
    match_fields: dict | None
    status: str
    created_at: str

@dataclass
class IngestResult:
    created: int         # 新建记录数
    merged: int          # 自动合并数
    pending: int         # 待确认数
    errors: int          # 失败数
    error_details: list[str]
```

### 关键方法行为说明

#### `ingest(candidate_data, platform)` 去重逻辑

1. 查询 `candidates` 表：`WHERE name=? AND current_company=? AND current_title=? AND COALESCE(city,'')=? AND COALESCE(education,'')=?`
2. 命中 → 自动合并：补充空字段（不覆盖已有值），新增 `source_profiles` 记录，返回已有 id
3. 未命中 → 查 `company_aliases` 做别名匹配（name + alias of company）
4. 别名命中 → 新建 candidates 记录 + 写入 `pending_merges`，返回新 id
5. 未命中 → 新建 candidates + source_profiles，返回新 id

#### `resolve_merge(pending_id, action)`

- `"merge"`: 将新数据合并到已有记录（同 ingest 的合并策略），删除新建的 candidates 记录（CASCADE 自动清理关联数据），更新 pending_merges 状态为 approved
- `"reject"`: 保留两条独立记录，更新 pending_merges 状态为 rejected

#### `enrich(candidate_id, detail_data)`

- 将 detail_data 写入 `candidate_details` 表（INSERT OR REPLACE）
- 自动重新判定 `data_level`（如有完整工作经历则升级为 detailed）
- 更新 `updated_at` 时间戳
- FTS 触发器自动同步索引

## 7. 入库流程

```
Chrome 插件导出 JSON / API 抓取数据
    │
    ▼
talent_db.batch_ingest(data, platform)
    │
    ├─ 标准化字段映射 (platform field → candidate field)
    │
    ├─ 逐条去重检测
    │   ├─ 完全匹配 → 合并 source_profile，补充空字段
    │   ├─ 疑似重复 → 新建记录 + pending_merges
    │   └─ 新记录   → 新建 candidates + source_profiles
    │
    ├─ 信息分级判定
    │   ├─ lead: 仅有基础信息
    │   ├─ core: 有 skills+education+work_years
    │   └─ detailed: 有完整工作经历
    │
    └─ 同步更新 FTS 索引
```

### 字段映射

```python
PLATFORM_FIELD_MAP = {
    "maimai": {
        "name": "name",
        "gender": "gender",
        "age": "age",
        "city": "city",
        "company": "current_company",
        "title": "current_title",
        "work_years": "work_years",
        "edu": "education",
        "skills": "skill_tags",
        "hunting_status": "hunting_status",
        "work_exp": "work_experience",
        "edu_exp": "education_experience",
    },
    "boss": {
        # 类似映射
    }
}
```

## 8. 文件结构

```
scripts/
├── talent_db.py          # 数据库接口（主模块）
├── talent_models.py      # dataclass 定义
├── talent_migrate.py     # 现有 JSON → SQLite 迁移脚本
└── data-manager.py       # (已有) 逐步迁移到 talent_db

tests/
├── test_talent_db.py     # 数据库接口测试
├── test_talent_models.py # 模型测试
└── test_talent_migrate.py# 迁移测试

data/
└── talent.db             # SQLite 数据库文件
```

## 9. 技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| 存储引擎 | SQLite | 1-10 万量级足够，Python 内置，零部署 |
| 全文搜索 | FTS5 | SQLite 内置，性能优秀（10 万条 <10ms） |
| 向量搜索 | sqlite-vec | 轻量 SQLite 扩展，支持 384 维向量 |
| Embedding 模型 | all-MiniLM-L6-v2 | 轻量（80MB），384 维，中英文可用 |
| 数据类 | dataclasses | Python 标准库，无额外依赖 |

## 10. 职责边界

| 模块 | 负责 | 不负责 |
|------|------|--------|
| `talent_db.py` | CRUD、去重、FTS 搜索、向量查询 | 评分计算、匹配逻辑、embedding 生成 |
| `talent_models.py` | 数据类定义 | 业务逻辑 |
| `talent_migrate.py` | JSON → SQLite 一次性迁移 | 持续同步 |
| SQLite + FTS5 + sqlite-vec | 存储、索引 | 业务逻辑 |
