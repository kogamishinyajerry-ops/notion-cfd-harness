# Phase5: Production Readiness & Operations 规划

**版本**: v1.1
**日期**: 2026-04-08
**状态**: Planning (Opus 审查: CONDITIONAL_PASS)
**Phase4 Gate**: ✅ COMPLETE (Baseline: 6be02a9)
**Opus 审查**: 修复 F-P5-001 至 F-P5-006

---

## 一、Phase5 目标

### 1.1 核心目标

Phase4 完成了 Governed Memory Network，实现了知识演化追踪、治理策略执行和 Memory-to-Code 映射。Phase5 的目标是实现 **Production Readiness & Operations（生产就绪与运维）**，确保系统可以：

1. **高性能运行**：优化查询性能、缓存策略、并发处理
2. **可观测性**：完善的监控、日志、指标、告警
3. **容灾能力**：备份、恢复、故障转移
4. **安全加固**：访问控制、审计日志、数据加密
5. **可运维性**：部署自动化、健康检查、故障排查

### 1.2 与 Phase4 的关系

| Phase4 产出 | Phase5 消费方式 |
|-------------|-----------------|
| MemoryNetwork | 性能优化、监控埋点 |
| VersionedKnowledgeRegistry | 备份策略、索引优化 |
| Gate 自动化 | CI/CD 集成、失败告警 |
| Notion 集成 | 连接池、重试机制 |
| CLI 工具 | 运维命令扩展 |

---

## 二、架构设计

### 2.1 Phase5 架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Phase5: Production Layer                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Phase4 Memory Network                        │   │
│  │                    (继承，无修改)                                │   │
│  └────────────────────────────┬────────────────────────────────────┘   │
│                               │                                         │
│         ┌─────────────────────┼─────────────────────┐                   │
│         ▼                     ▼                     ▼                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐             │
│  │  Performance │    │   Observabi- │    │    Security  │             │
│  │    Layer     │    │     lity     │    │    Layer     │             │
│  │              │    │              │    │              │             │
│  │ - Caching    │    │ - Metrics    │    │ - Access     │             │
│  │ - Indexing   │    │ - Logging    │    │   Control    │             │
│  │ - Pooling    │    │ - Tracing    │    │ - Audit      │             │
│  │ - Async      │    │ - Alerts    │    │ - Encryption │             │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘             │
│         │                    │                    │                     │
│         └────────────────────┼────────────────────┘                     │
│                              ▼                                          │
│                 ┌──────────────────────┐                               │
│                 │   Operations Layer   │                               │
│                 │                      │                               │
│                 │ - Backup/Recovery    │                               │
│                 │ - Health Checks      │                               │
│                 │ - CI/CD Integration  │                               │
│                 │ - Deployment         │                               │
│                 └──────────────────────┘                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Infrastructure                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │   Monitoring │  │    Logging   │  │    Alerting  │                 │
│  │   (Prometheus)│  │   (ELK/Loki) │  │   (PagerDuty)│                 │
│  └──────────────┘  └──────────────┘  └──────────────┘                 │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │    Backup    │  │     CI/CD    │  │  Deployment  │                 │
│  │   (S3/GCS)   │  │  (GitHub Actions)│ │  (Docker/K8s)│              │
│  └──────────────┘  └──────────────┘  └──────────────┘                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Manager 组合模式（中间件链）

**修复 F-P5-001**: 定义 Manager 调用顺序，采用中间件链模式：

```python
class MiddlewareChain:
    """
    中间件链：Security → Observability → Performance → Core

    调用顺序：
    1. SecurityManager: 检查权限，记录审计
    2. ObservabilityManager: 记录指标，设置 tracing context
    3. PerformanceManager: 检查缓存，获取连接池
    4. MemoryNetwork (Core): 执行核心逻辑
    """
    def __init__(self, core: MemoryNetwork):
        self.security = SecurityManager()
        self.observability = ObservabilityManager()
        self.performance = PerformanceManager()
        self.core = core

    async def register_change(self, user: str, unit_id: str, content: Any, metadata: dict) -> dict:
        # 1. Security: 检查权限
        if not self.security.check_permission(user, "write", f"unit:{unit_id}"):
            raise PermissionDenied(user, "write", f"unit:{unit_id}")

        # 2. Observability: 开始 span
        with self.observability.tracer.start_span("register_change") as span:
            span.set_attribute("unit_id", unit_id)

            # 3. Performance: 检查缓存
            cached = await self.performance.get_cached_node(unit_id)
            if cached and cached.version == metadata.get("based_on_version"):
                return {"cached": True, "node": cached}

            # 4. Core: 执行核心逻辑
            result = await self.core.register_change_async(unit_id, content, metadata)

            # 5. Observability: 记录指标
            self.observability.record_metric("register_change_duration", ..., tags={"unit": unit_id})

            return result
```

### 2.3 新增组件设计

```python
# P5-01: Performance Manager
class PerformanceManager:
    """性能优化管理器"""
    def __init__(self):
        self.cache = CacheLayer()
        self.index = IndexManager()
        self.pool = ConnectionPool()

    async def get_cached_node(self, unit_id: str) -> MemoryNode | None
    def rebuild_indexes(self) -> dict

# P5-02: Observability Manager
class ObservabilityManager:
    """可观测性管理器"""
    def __init__(self):
        self.metrics = MetricsCollector()
        self.logger = StructuredLogger()
        self.tracer = DistributedTracer()

    def record_metric(self, name: str, value: float, tags: dict)
    def emit_event(self, event: dict)

# P5-03: Security Manager
class SecurityManager:
    """安全管理器"""
    def __init__(self):
        self.authz = AccessControl()
        self.audit = AuditLogger()
        self.crypto = EncryptionService()

    def check_permission(self, user: str, action: str, resource: str) -> bool
    def log_audit_event(self, event: AuditEvent)

# P5-04: Operations Manager
class OperationsManager:
    """运维管理器"""
    def __init__(self):
        self.backup = BackupManager()
        self.health = HealthChecker()
        self.recovery = RecoveryManager()

    def create_backup(self) -> BackupHandle
    def health_check(self) -> HealthStatus
    def restore_from_backup(self, handle: BackupHandle) -> bool
```

---

## 三、任务分解 (P5-01 ~ P5-12)

### 3.1 性能层任务 (P5-01 ~ P5-03)

| 任务 ID | 任务名称 | 执行模型 | 依赖 | Code Review |
|---------|----------|----------|------|-------------|
| P5-01 | Cache Layer - 两级缓存（L1 cachetools + L2 可选 Redis） | Codex | P4-06 | Codex CR |
| P5-02 | Index Manager - 版本历史索引优化 | Codex | P4-01 | Codex CR |
| P5-03 | Async 重构 + Connection Pool - 核心路径 async 化 + Notion API 连接池 | Codex | P4-09 | Codex CR |

**修复 F-P5-003, F-P5-004**：
- P5-01 采用两级缓存：默认 L1 进程内（`cachetools.TTLCache`），L2 Redis 可选
- P5-03 增加 async 重构子任务，核心查询路径 async 化，支持 100+ QPS

### 3.2 可观测性任务 (P5-04 ~ P5-06)

| 任务 ID | 任务名称 | 执行模型 | 依赖 | Code Review |
|---------|----------|----------|------|-------------|
| P5-04 | Metrics Collection - Prometheus 集成（为 Health Checks 提供指标） | Codex | P4-06 | Codex CR |
| P5-05 | Structured Logging - JSON 结构化日志 + correlation_id | Codex | P4-06 | Codex CR |
| P5-06 | Request Tracing - 轻量级追踪（structlog + correlation_id）| Codex | P5-05 | Codex CR |

**修复 F-P5-002**：
- P5-06 从 OpenTelemetry 降级为轻量级方案（`structlog + correlation_id`）
- OpenTelemetry 标记为 Phase6 延期项（当系统拆分为多服务时再引入）

### 3.3 安全任务 (P5-07 ~ P5-08)

| 任务 ID | 任务名称 | 执行模型 | 依赖 | Code Review |
|---------|----------|----------|------|-------------|
| P5-07 | Access Control - AuthN + RBAC 权限系统 + Secret 管理 | Codex | P4-06 | Codex CR + Opus |
| P5-08 | Audit Logging - 审计日志系统 | Codex | P5-07 | Codex CR |

**修复 F-P5-006 (P0)**：
- P5-07 增加认证（AuthN）子节：
  - CLI 模式：信任 OS 用户（`os.getlogin()`）
  - API 模式：Bearer token 或 API key header（预留，Phase5 不暴露 HTTP API）
- 增加 Secret 管理策略：
  - 优先级：环境变量 > `~/.notion_key` > 硬编码（禁止）
  - Notion API key、Codex API key 从环境变量读取

### 3.4 运维任务 (P5-09 ~ P5-12)

| 任务 ID | 任务名称 | 执行模型 | 依赖 | Code Review |
|---------|----------|----------|------|-------------|
| P5-09 | Backup & Recovery - 备份恢复系统 | Codex | P4-01 | Codex CR |
| P5-10 | Health Checks - 健康检查系统（集成 P5-04 Metrics）| Codex | P5-04, P4-06 | Codex CR |
| P5-11 | CI/CD Integration - GitHub Actions 工作流 | Codex | P5-10 | Codex CR |
| P5-12 | 运维文档 + Phase5 Baseline | Codex | P5-11 | 跳过 CR |

---

## 四、执行流程（含 Code Review）

### 4.1 单任务执行流程

```
1. 用户请求: "执行 P5-01 Cache Layer"
   ↓
2. Claude Code 检查 Codex 状态
   ↓
3. 用 Codex 执行实现
   ↓
4. 实现完成 → 触发 Codex Code Review
   ├─ 有额度 → 触发 review
   │  ├─ PASS → 继续
   │  ├─ CONDITIONAL PASS → 记录建议，继续
   │  └─ BLOCKED → 修复，重新审查
   └─ 无额度 → 跳过 CR，记录 SKIPPED
   ↓
5. 运行性能基准测试（如适用）
   ↓
6. Git commit (带 Co-Authored-By)
   ↓
7. 推送 GitHub
   ↓
8. 更新 Notion 任务状态
```

### 4.2 Code Review 触发脚本（复用 Phase4）

使用 `scripts/trigger_code_review.sh`，已在 Phase4 配置完成。

---

## 五、Codex Code Review 降级策略

### 5.1 复用 Phase4 策略

Phase5 复用 Phase4 的降级策略：
- 非阻塞触发：额度不足不阻塞执行
- SKIPPED 记录：记录到 Notion Reviews DB
- 后续补充：可事后补充审查

### 5.2 P5-07 特殊处理

P5-07 (Access Control) 涉及安全，需要 **Opus 架构审查**：
- 完成 Codex Code Review 后
- 停下来，给用户 Opus 审查提示词
- 等用户手动 @Notion AI 里的 Opus 4.6
- 获得回复并返回粘贴，才允许继续

---

## 六、性能指标

### 6.1 性能目标

| 指标 | 当前 (Phase4) | 目标 (Phase5) | 测量方式 |
|------|--------------|---------------|----------|
| 版本查询延迟 | ~50ms | <10ms (p99) | Prometheus |
| 网络状态查询 | ~200ms | <50ms (p99) | Prometheus |
| 并发请求 | 1 | 100+ QPS | Load Test |
| 内存占用 | ~100MB | <200MB | Metrics |
| 缓存命中率 | 0% | >80% | Cache Stats |

### 6.2 基准测试

```python
# tests/bench/test_performance.py
def test_version_query_performance():
    """版本查询性能基准"""
    network = MemoryNetwork()

    start = time.time()
    for _ in range(1000):
        network.get_version("FORM-009", "v1.0")
    elapsed = time.time() - start

    assert elapsed < 1.0  # 1000 queries in <1s
```

---

## 七、监控设计

### 7.1 核心指标

**业务指标**：
- `memory_network_nodes_total`: 网络节点总数
- `memory_network_changes_total`: 变更总数
- `gate_results_total`: Gate 结果计数（按状态分组）
- `code_mappings_total`: 代码映射总数

**性能指标**：
- `version_query_duration_seconds`: 版本查询延迟
- `propagation_duration_seconds`: 传播延迟
- `notion_api_request_duration_seconds`: Notion API 请求延迟
- `cache_hit_ratio`: 缓存命中率

**错误指标**：
- `errors_total`: 错误总数（按类型分组）
- `gate_failures_total`: Gate 失败计数
- `notion_api_errors_total`: Notion API 错误计数

### 7.2 告警规则

```yaml
# alerting_rules.yml
groups:
  - name: memory_network
    rules:
      - alert: HighErrorRate
        expr: rate(errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate in Memory Network"

      - alert: CacheHitRatioLow
        expr: cache_hit_ratio < 0.8
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Cache hit ratio below 80%"

      - alert: NotionAPIFailure
        expr: rate(notion_api_errors_total[1m]) > 1
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Notion API failing"
```

---

## 八、安全设计

### 8.1 认证（AuthN）

**修复 F-P5-006 (P0)**：增加认证机制

```python
from enum import Enum
import os

class AuthMode(Enum):
    CLI = "cli"
    API = "api"

class AuthManager:
    """认证管理器"""
    def __init__(self, mode: AuthMode = AuthMode.CLI):
        self.mode = mode

    def authenticate(self, token: str | None = None) -> str:
        """
        认证并返回用户标识

        CLI 模式：信任 OS 用户（os.getlogin()）
        API 模式：验证 Bearer token（预留，Phase5 不暴露 HTTP API）
        """
        if self.mode == AuthMode.CLI:
            # CLI 模式：信任 OS 用户
            return os.getlogin()
        elif self.mode == AuthMode.API:
            # API 模式：验证 Bearer token
            if not token:
                raise Unauthorized("Missing token")
            return self._validate_token(token)
        else:
            raise ValueError(f"Unknown auth mode: {self.mode}")

    def _validate_token(self, token: str) -> str:
        """验证 API token（预留）"""
        # Phase5 不实现，返回用户标识
        # Phase6: 验证 JWT 或 API key
        return "user_from_token"
```

### 8.2 Secret 管理

```python
class SecretManager:
    """密钥管理器"""
    @staticmethod
    def get_notion_api_key() -> str:
        """获取 Notion API Key

        优先级：
        1. 环境变量 NOTION_API_KEY
        2. ~/.notion_key 文件
        3. 抛出错误（禁止硬编码）
        """
        key = os.environ.get("NOTION_API_KEY")
        if key:
            return key

        key_file = Path.home() / ".notion_key"
        if key_file.exists():
            return key_file.read_text().strip()

        raise ValueError("NOTION_API_KEY not found in environment or ~/.notion_key")

    @staticmethod
    def get_codex_api_key() -> str:
        """获取 Codex API Key（类似逻辑）"""
        key = os.environ.get("CODEX_API_KEY")
        if key:
            return key
        # ... 从配置文件读取
```

### 8.3 RBAC 权限模型

```python
@dataclass
class Permission:
    resource: str      # "memory_network", "gates", "versions"
    action: str        # "read", "write", "admin"
    condition: dict | None = None

@dataclass
class Role:
    name: str
    permissions: List[Permission]

# 预定义角色
ROLES = {
    "viewer": Role("viewer", [
        Permission("memory_network", "read"),
        Permission("versions", "read"),
    ]),
    "operator": Role("operator", [
        Permission("memory_network", "read"),
        Permission("memory_network", "write"),
        Permission("gates", "read"),
        Permission("versions", "read"),
    ]),
    "admin": Role("admin", [
        Permission("*", "*"),  # 全部权限
    ]),
}
```

### 8.2 审计日志

```python
@dataclass
class AuditEvent:
    timestamp: datetime
    user: str
    action: str
    resource: str
    outcome: str  # "success" | "failure"
    details: dict
    ip_address: str | None = None
    user_agent: str | None = None

# 审计事件必须记录：
# - 所有 Gate 触发
# - 所有版本变更
# - 所有权限修改
# - 所有备份/恢复操作
```

---

## 九、CI/CD 集成

### 9.1 GitHub Actions 工作流

```yaml
# .github/workflows/phase5-ci.yml
name: Phase5 CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Run tests
        run: |
          pytest tests/test_p4_*.py tests/test_p5_*.py -v
      - name: Run performance benchmarks
        run: |
          pytest tests/bench/test_performance.py --benchmark-json=output.json
      - name: Upload metrics
        run: |
          # 上传到 Prometheus Pushgateway

  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Bandit
        run: bandit -r knowledge_compiler/
      - name: Run Safety
        run: safety check

  deploy:
    needs: [test, security-scan]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy
        run: |
          # 部署逻辑
```

### 9.2 Gate 自动化

```yaml
# .github/workflows/gate-check.yml
name: Gate Check

on:
  push:
    paths:
      - 'knowledge_compiler/**'
      - 'tests/test_p4_*.py'
      - 'tests/test_p5_*.py'

jobs:
  g3-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run G3 Gate
        run: |
          ./scripts/memory-network gate trigger G3 --record-path reports/g3-result.json
      - name: Upload result
        uses: actions/upload-artifact@v3
        with:
          name: g3-result
          path: reports/g3-result.json
```

---

## 十、备份与恢复

### 10.1 备份策略

**备份内容**：
- `.versions.json` (版本数据库)
- Notion Reviews DB 导出
- Notion Events DB 导出
- 代码映射状态

**备份频率**：
- 增量备份：每小时
- 完整备份：每天

**保留策略**：
- 每日备份保留 30 天
- 每周备份保留 12 周
- 每月备份保留 12 个月

### 10.2 恢复目标（RTO/RPO）

**修复 Minor 发现**：定义恢复目标和恢复点目标

| 指标 | 目标 | 说明 |
|------|------|------|
| **RTO** (Recovery Time Objective) | < 30 分钟 | 从故障发生到服务恢复的最大时间 |
| **RPO** (Recovery Point Objective) | < 1 小时 | 可能丢失的数据最大时间范围 |

**计算依据**：
- 每小时增量备份 → 最坏情况丢失 1 小时数据
- 完整备份恢复时间约 15-20 分钟 → RTO 30 分钟留有余量

### 10.3 恢复流程

```python
def restore_from_backup(backup_handle: BackupHandle) -> bool:
    """
    从备份恢复系统状态

    1. 验证备份完整性
    2. 停止写入操作
    3. 恢复版本数据库
    4. 恢复 Notion 状态（如需要）
    5. 验证恢复后的状态
    6. 恢复写入操作
    """
    pass
```

---

## 十一、质量标准

### 11.1 代码质量（Codex CR 检查）

- PEP8 合规
- 类型注解完整
- Docstring 覆盖率 > 80%
- 单元测试覆盖率 > 70%
- 性能测试覆盖率 > 50%

### 11.2 架构质量（Opus 审查）

- 与 Phase4 Memory Network 一致性
- 无循环依赖
- 接口清晰，职责单一
- 错误处理完善
- 安全性考虑

### 11.3 运维质量

- 健康检查覆盖所有组件
- 告警规则覆盖所有关键指标
- 文档覆盖所有运维操作
- 故障排查手册完整

---

## 十二、风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| 性能优化效果不达预期 | 基准测试先行，分阶段优化 |
| 监控指标缺失或误报 | 充分测试告警规则 |
| Notion API 限流 | 连接池 + 重试 + 降级 |
| 备份恢复失败 | 定期演练恢复流程 |
| 安全漏洞引入 | Opus 审查 + 安全扫描 |

---

## 十三、验收标准

### 13.1 Phase5 Gate 条件

- [ ] P5-01 ~ P5-11 所有任务完成
- [ ] 性能基准测试通过（满足目标指标）
- [ ] 监控告警配置完成
- [ ] 备份恢复演练成功
- [ ] 安全扫描通过
- [ ] CI/CD 流程运行正常
- [ ] Opus 架构审查通过（P5-07）

### 13.2 最终交付物

1. `knowledge_compiler/performance/` - 性能层模块
2. `knowledge_compiler/observability/` - 可观测性模块
3. `knowledge_compiler/security/` - 安全模块
4. `knowledge_compiler/operations/` - 运维模块
5. `.github/workflows/` - CI/CD 配置
6. Phase5_BASELINE_MANIFEST.json
7. PHASE5_OPERATIONS.md - 运维手册
8. 监控告警配置文件

---

## 十四、下一步行动

**立即执行**：

1. 更新 Notion Phase5 项目页
2. 开始 P5-01: Cache Layer
3. 配置性能基准测试

---

## 十五、Opus 审查记录

### 15.1 审查结果

**审查官**: CFDJerry (Opus 4.6)
**审查日期**: 2026-04-08
**审查结果**: CONDITIONAL_PASS
**规划版本**: v1.0 → v1.1（已修复）

### 15.2 发现的问题与修复

| 编号 | 描述 | 级别 | 修复状态 |
|------|------|------|----------|
| F-P5-001 | Manager 调用顺序未定义 | Medium | ✅ 已修复 - §2.2 增加中间件链模式 |
| F-P5-002 | OpenTelemetry 选型偏重 | Medium | ✅ 已修复 - P5-06 降级为 structlog |
| F-P5-003 | Redis 运维复杂度 | Minor | ✅ 已修复 - P5-01 两级缓存 |
| F-P5-004 | 100+ QPS 需 async 重造 | Medium | ✅ 已修复 - P5-03 增加 async 子任务 |
| F-P5-005 | P5-04/P5-10 功能重叠 | Minor | ✅ 已修复 - P5-10 集成 P5-04 |
| F-P5-006 | 认证（AuthN）缺失 | High | ✅ 已修复 - §8.1 增加 AuthManager |

### 15.3 延期到 Phase6

- OpenTelemetry 分布式追踪（当系统拆分为多服务时再引入）
- HTTP API 模式的 Bearer token 认证（Phase5 只用 CLI 模式）

---

*规划版本历史*:
- v1.0: 初始规划
- v1.1: 修复 Opus 审查发现（F-P5-001 至 F-P5-006）

---

*规划者: Claude Code (Opus 4.6 架构指导)*
*规划版本: v1.0*
*创建时间: 2026-04-08*
*基于: Phase4 Baseline (6be02a9)*
