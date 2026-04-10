# 反爬策略参考

本文档定义在使用 maimai-scraper 技能时应遵循的反爬规避策略，以降低被封禁风险。

## 核心原则

1. **模拟人类行为**：所有操作都应像真人使用一样
2. **控制频率**：避免高频请求触发风控
3. **保持会话**：复用登录状态，减少重复登录
4. **优雅降级**：遇到限制时自动暂停，而非强行突破

## 策略详情

### 1. 请求间隔控制

```
策略：每次操作后随机等待

具体参数：
┌────────────────────┬────────────────────┐
│ 操作类型            │ 等待时间            │
├────────────────────┼────────────────────┤
│ 页面跳转/刷新       │ 2-4 秒             │
│ 点击操作            │ 1-3 秒             │
│ 表单输入            │ 0.5-1.5 秒         │
│ 翻页操作            │ 3-5 秒             │
│ 打开详情页          │ 2-3 秒             │
│ 关闭详情页          │ 1-2 秒             │
└────────────────────┴────────────────────┘

实现方式：
  - 使用随机值，避免固定间隔
  - 在关键操作间插入 wait
  - 可根据实际情况动态调整
```

### 2. 并发控制

```
策略：限制同时打开的详情页数量

参数：
  - 最大并发数：2-3 个
  - 原因：同时打开过多详情页会触发异常行为检测

实现：
  1. 从列表页获取候选人链接列表
  2. 每次取 2-3 个链接
  3. 并发派发 subagent 获取详情
  4. 等待所有 subagent 完成
  5. 再取下一批 2-3 个
  6. 循环直到处理完毕
```

### 3. 模拟人类行为

```
策略：让自动化行为更接近真人

具体措施：
  - 鼠标移动：点击前先移动到目标位置
  - 滚动页面：翻页前适当滚动浏览
  - 输入速度：表单输入不要太快，有自然停顿
  - 随机停顿：偶尔暂停几秒"思考"
  - 浏览轨迹：不要直接跳转，先看到内容再操作
```

### 4. 会话保持

```
策略：复用登录状态，减少登录频率

实现：
  - 使用 agent-browser 的 session 保持功能
  - 保存 cookies 和 localStorage
  - 避免频繁退出登录
  - 如果检测到登录失效，暂停并提示用户重新登录
```

### 5. 失败重试机制

```
策略：遇到异常时优雅处理，而非无限重试

重试规则：
┌────────────────────┬────────────────────┐
│ 异常类型            │ 处理方式            │
├────────────────────┼────────────────────┤
│ 网络超时            │ 等待 5 秒后重试，最多 3 次 │
│ 页面加载失败        │ 刷新页面重试，最多 2 次  │
│ 元素找不到          │ 等待 2 秒后重试，最多 3 次 │
│ 登录失效            │ 暂停，提示用户重新登录   │
│ 频率限制（验证码）   │ 暂停，等待用户处理      │
│ 账号异常            │ 停止抓取，保存已抓取数据  │
└────────────────────┴────────────────────┘

重试间隔：指数退避（2s -> 4s -> 8s）
```

### 6. 风险检测与响应

```
需要检测的风险信号：
  - 出现验证码
  - 页面跳转到登录页
  - 出现"操作频繁"提示
  - 页面内容异常（空白、错误信息）
  - 请求超时

响应策略：
  1. 立即停止当前操作
  2. 截图保存现场
  3. 通知用户异常情况
  4. 保存已抓取的数据
  5. 等待用户指示是否继续
```

### 7. 单次抓取限制

```
建议限制：
  - 单次最多抓取：200-300 位候选人
  - 单次最长运行：30-45 分钟
  - 翻页间隔：建议每 5 页休息 10-20 秒

超过限制时：
  - 主动暂停
  - 询问用户是否继续
  - 保存当前进度
```

## 实现伪代码

```typescript
// 反爬策略工具函数

// 随机等待
async function randomWait(minSec: number, maxSec: number) {
  const waitTime = (minSec + Math.random() * (maxSec - minSec)) * 1000;
  await sleep(waitTime);
}

// 带重试的操作
async function withRetry<T>(
  operation: () => Promise<T>,
  maxRetries: number = 3,
  backoffMs: number = 2000
): Promise<T> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await operation();
    } catch (error) {
      if (i === maxRetries - 1) throw error;
      await sleep(backoffMs * Math.pow(2, i));
    }
  }
  throw new Error('Unreachable');
}

// 检测风险信号
async function detectRiskSignals(page: Page): Promise<string | null> {
  const content = await page.content();

  if (content.includes('验证码') || content.includes('captcha')) {
    return 'CAPTCHA_DETECTED';
  }
  if (content.includes('操作频繁') || content.includes('请稍后再试')) {
    return 'RATE_LIMITED';
  }
  if (content.includes('请登录') && !content.includes('退出')) {
    return 'SESSION_EXPIRED';
  }

  return null;
}

// 并发控制
async function processBatch<T, R>(
  items: T[],
  processor: (item: T) => Promise<R>,
  concurrency: number = 3
): Promise<R[]> {
  const results: R[] = [];

  for (let i = 0; i < items.length; i += concurrency) {
    const batch = items.slice(i, i + concurrency);
    const batchResults = await Promise.all(
      batch.map(item => processor(item))
    );
    results.push(...batchResults);

    // 批次间等待
    await randomWait(2, 4);
  }

  return results;
}
```

## 注意事项

1. **不要试图绕过验证码**：验证码出现时应暂停并等待用户处理
2. **不要使用代理池**：脉脉可能检测到 IP 频繁切换
3. **不要在非工作时间抓取**：凌晨抓取更容易触发风控
4. **遵守 robots.txt**：尊重网站的爬虫协议
5. **数据仅限自用**：不要将抓取的数据用于商业分发

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

### 启动脚本

```powershell
# 启动 daemon
.\adapters\claude-code\scripts\start-daemon.ps1

# 检查登录状态
.\adapters\claude-code\scripts\check-session.ps1
```

### Windows 注意事项

- 必须使用 headed 模式（`AGENT_BROWSER_HEADED=1`）
- PowerShell 脚本可能需要执行策略调整：`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
- 密钥文件权限通过 icacls 设置为仅当前用户可读

### Session 持久化流程

```
首次使用:
1. start-daemon.ps1 → 生成密钥 → 启动 daemon
2. 用户扫码登录 → session 自动加密保存

后续使用:
1. start-daemon.ps1 → 读取密钥 → 恢复 session
2. check-session.ps1 → 验证登录状态
3. 如果过期 → 提示重新登录
```

## 免责声明

本技能仅供合法招聘用途，用户需自行承担使用风险。请遵守脉脉用户协议和相关法律法规。
