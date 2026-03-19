# 脉脉登录持久化方案设计

**日期**: 2026-03-19
**状态**: ✅ 已实现
**作者**: Claude + 用户

## 背景

### 问题
- 用户使用 maimai-scraper skill 时每次需要重新登录脉脉
- 脉脉网页端仅支持手机验证码登录和 APP 扫码登录
- 频繁登录影响用户体验和自动化流程的效率

### 目标
- 实现登录状态持久化，减少重复登录频率
- 在合理的安全范围内保护用户登录凭据
- 保持与现有 agent-browser 架构的兼容性

## 方案设计

### 核心方案：daemon 模式 + session 持久化

1. **daemon 模式**：保持浏览器实例在后台持续运行，避免每次启动浏览器
2. **session 持久化**：自动保存 cookies/localStorage，即使 daemon 重启也能恢复

### 架构图

```
┌─────────────────────────────────────────────────────┐
│  agent-browser daemon (后台持续运行)                  │
│  └─ session: maimai-talent                          │
│     └─ cookies + localStorage (加密存储)             │
└─────────────────────────────────────────────────────┘
         ↑
         │ HTTP IPC
         │
┌─────────────────────────────────────────────────────┐
│  maimai-scraper skill                               │
│  └─ 连接 daemon → 检测登录状态 → 执行搜索             │
└─────────────────────────────────────────────────────┘
```

### 数据流

```
用户调用 skill
    │
    ▼
检查 daemon 是否运行 ──否──▶ 启动 daemon
    │
    是
    ▼
检查 session 登录状态 ──未登录──▶ 提示用户扫码/验证码
    │
    已登录
    ▼
执行搜索任务
    │
    ▼
自动保存 session 变更
```

## 需要修改的文件

### 1. `scripts/start-daemon.ps1`（新增）

daemon 启动脚本，负责：
- 检查是否已有 daemon 运行
- 生成或读取加密密钥
- 启动 agent-browser daemon

```powershell
# scripts/start-daemon.ps1

$DaemonUrl = "http://localhost:3000"
$KeyPath = "$env:USERPROFILE\.agent-browser\maimai-key"
$SessionName = "maimai-talent"

# 检查 daemon 是否已运行
try {
    $response = Invoke-RestMethod -Uri "$DaemonUrl/health" -TimeoutSec 2
    if ($response.status -eq "ok") {
        Write-Host "Daemon already running at $DaemonUrl"
        exit 0
    }
} catch {
    # Daemon 未运行，继续启动
}

# 确保密钥文件存在
$KeyDir = Split-Path $KeyPath -Parent
if (-not (Test-Path $KeyDir)) {
    New-Item -ItemType Directory -Path $KeyDir -Force | Out-Null
}

if (-not (Test-Path $KeyPath)) {
    # 生成 32 字节随机密钥
    $key = [Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
    $key | Out-File -FilePath $KeyPath -Encoding utf8 -NoNewline
    # 设置权限为仅当前用户可读
    icacls $KeyPath /inheritance:r /grant:r "$env:USERNAME:R" | Out-Null
    Write-Host "Generated new encryption key at $KeyPath"
}

# 设置环境变量
$env:AGENT_BROWSER_ENCRYPTION_KEY = Get-Content $KeyPath
$env:AGENT_BROWSER_HEADED = "1"
$env:AGENT_BROWSER_PORT = "3000"

# 启动 daemon
Write-Host "Starting agent-browser daemon..."
agent-browser daemon start

# 等待 daemon 就绪
$retries = 0
while ($retries -lt 10) {
    try {
        Invoke-RestMethod -Uri "$DaemonUrl/health" -TimeoutSec 1 | Out-Null
        Write-Host "Daemon started successfully at $DaemonUrl"
        exit 0
    } catch {
        Start-Sleep -Seconds 1
        $retries++
    }
}

Write-Error "Failed to start daemon after 10 seconds"
exit 1
```

### 2. `scripts/check-session.ps1`（新增）

会话检查脚本，负责：
- 检测 daemon 运行状态
- 检测脉脉登录状态
- 返回状态信息

```powershell
# scripts/check-session.ps1

$DaemonUrl = "http://localhost:3000"
$SessionName = "maimai-talent"

# 检查 daemon 状态
try {
    $health = Invoke-RestMethod -Uri "$DaemonUrl/health" -TimeoutSec 2
    Write-Host "Daemon status: running"
} catch {
    Write-Host "Daemon status: not running"
    Write-Host "Run .\scripts\start-daemon.ps1 to start"
    exit 1
}

# 检查 session 状态
try {
    $session = Invoke-RestMethod -Uri "$DaemonUrl/sessions/$SessionName" -TimeoutSec 5

    # 检查脉脉登录状态
    $body = @{
        session = $SessionName
        url = "https://maimai.cn"
        action = "evaluate"
        script = "document.cookie.includes('u')"
    } | ConvertTo-Json

    $result = Invoke-RestMethod -Uri "$DaemonUrl/browser/evaluate" `
        -Method POST `
        -Body $body `
        -ContentType "application/json"

    if ($result.result -eq $true) {
        Write-Host "Maimai login status: logged in"
        exit 0
    } else {
        Write-Host "Maimai login status: not logged in"
        Write-Host "Please login via the browser window"
        exit 2
    }
} catch {
    Write-Host "Session status: not found or error"
    Write-Host "Error: $_"
    exit 1
}
```

### 3. `SKILL.md`（更新）

更新 Phase 1 登录验证流程：

```markdown
## Phase 1: 登录验证

### 1.1 检查 Daemon 状态
```powershell
.\scripts\check-session.ps1
```

- 返回码 0：已登录，可直接使用
- 返回码 1：daemon 未运行，需先运行 `.\scripts\start-daemon.ps1`
- 返回码 2：未登录，需在浏览器窗口中扫码

### 1.2 首次使用流程
1. 运行 `.\scripts\start-daemon.ps1` 启动 daemon
2. daemon 会打开浏览器窗口
3. 访问 https://maimai.cn 并使用 APP 扫码登录
4. 登录成功后 session 自动保存
5. 后续使用无需重复登录

### 1.3 Session 恢复
- daemon 重启后会自动恢复 session
- 如果 cookies 过期，需重新扫码登录
```

### 4. `references/anti-scraping.md`（补充）

添加 daemon 配置章节：

```markdown
## Daemon 配置

### 环境变量

| 变量 | 值 | 说明 |
|------|-----|------|
| `AGENT_BROWSER_HEADED` | `1` | headless 模式下 cookie 刷新有问题 |
| `AGENT_BROWSER_PORT` | `3000` | daemon 监听端口 |
| `AGENT_BROWSER_ENCRYPTION_KEY` | (自动生成) | session 加密密钥 |

### 文件位置

| 文件 | 路径 | 说明 |
|------|------|------|
| 加密密钥 | `~/.agent-browser/maimai-key` | AES-256-GCM 密钥 |
| Session 数据 | `~/.agent-browser/sessions/` | 加密存储的 cookies |

### Windows 注意事项
- 必须使用 headed 模式（`AGENT_BROWSER_HEADED=1`）
- PowerShell 脚本可能需要执行策略调整
- 密钥文件权限通过 icacls 设置
```

## 工作流程

### 首次使用

```
1. 用户运行 start-daemon.ps1
   │
   ├─▶ 检查 daemon 状态
   │
   ├─▶ 生成加密密钥（如果不存在）
   │
   ├─▶ 设置环境变量
   │
   └─▶ 启动 agent-browser daemon
       │
       └─▶ 打开浏览器窗口

2. 用户在浏览器中登录脉脉
   │
   └─▶ daemon 自动保存 session（加密）

3. 用户调用 maimai-scraper skill
   │
   └─▶ 检测到已登录，直接执行搜索
```

### 后续使用

```
1. 用户运行 start-daemon.ps1（如果 daemon 未运行）
   │
   └─▶ daemon 恢复已保存的 session

2. 用户调用 skill
   │
   ├─▶ 检测登录状态
   │
   ├─▶ 如果已登录：直接执行
   │
   └─▶ 如果过期：提示重新登录
```

## 安全考虑

### 加密方案
- 使用 AES-256-GCM 加密 session 数据
- 密钥为 32 字节随机数，Base64 编码存储
- 加密实现参考 `~/.claude/skills/learned/aes-256-gcm-encryption-pattern.md`

### 密钥管理
- 密钥存储在 `~/.agent-browser/maimai-key`
- 文件权限设置为 600（仅当前用户可读）
- Windows 通过 `icacls` 设置权限

### Git 忽略
在 `.gitignore` 中添加：
```
.agent-browser/
*.key
```

### 安全边界
- 密钥文件不应提交到版本控制
- 不在日志中输出密钥内容
- Session 数据仅在本地存储

## Windows 兼容性

### 环境要求
- PowerShell 5.1+ 或 PowerShell Core 7+
- agent-browser 已安装并添加到 PATH

### 已知问题
- headless 模式下 cookie 刷新不正常，必须使用 headed 模式
- 浏览器窗口会保持打开状态

### 脚本格式
- 所有脚本使用 `.ps1` 格式
- 路径使用 `$env:USERPROFILE` 而非 `~`

## 实现计划

| 阶段 | 任务 | 优先级 |
|------|------|--------|
| 1 | 创建 start-daemon.ps1 | P0 |
| 2 | 创建 check-session.ps1 | P0 |
| 3 | 更新 SKILL.md | P1 |
| 4 | 更新 anti-scraping.md | P1 |
| 5 | 测试完整流程 | P0 |
| 6 | 添加 .gitignore 条目 | P1 |

## 相关参考

- [agent-browser 架构](https://github.com/vercel-labs/agent-browser)
- `~/.claude/skills/learned/client-daemon-ipc-architecture.md`
- `~/.claude/skills/learned/aes-256-gcm-encryption-pattern.md`

## 设计决策记录

### 为什么使用 daemon 模式？
- 避免每次启动浏览器的开销
- 保持登录状态不丢失
- 与 agent-browser 架构一致

### 为什么需要加密？
- 脉脉 cookies 包含敏感的身份信息
- 防止本地其他用户窃取 session
- 符合安全最佳实践

### 为什么使用 PowerShell？
- Windows 原生支持
- 无需额外安装依赖
- 便于用户理解和修改

---

## 实现记录 (2026-03-19)

### 已完成

| 任务 | 文件 | 状态 |
|------|------|------|
| 启动脚本 | `adapters/claude-code/scripts/start-daemon.ps1` | ✅ |
| 检查脚本 | `adapters/claude-code/scripts/check-session.ps1` | ✅ |
| SKILL.md 更新 | `adapters/claude-code/skills/maimai-scraper/SKILL.md` | ✅ |
| 反爬文档更新 | `references/anti-scraping.md` | ✅ |
| .gitignore | 根目录 `.gitignore` | ✅ |

### 实际实现方案

使用 agent-browser 的 `--profile` 和 `--session-name` 参数实现持久化：

```powershell
# 启动（会打开浏览器窗口）
agent-browser --profile ~/.agent-browser/maimai-profile --session-name maimai-talent --headed open "https://maimai.cn"
```

### 文件位置

| 文件 | 路径 |
|------|------|
| Profile 数据 | `~/.agent-browser/maimai-profile/` |
| Session 状态 | `~/.agent-browser/sessions/maimai-talent/` |
| 加密密钥 | `~/.agent-browser/maimai-key` |

### 使用方法

```powershell
# 1. 首次使用：启动浏览器并登录
.\adapters\claude-code\scripts\start-daemon.ps1

# 2. 在浏览器中扫码登录脉脉

# 3. 后续使用：session 会自动恢复
# 直接调用 maimai-scraper skill 即可
```
