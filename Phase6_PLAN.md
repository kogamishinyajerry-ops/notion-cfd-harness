# Phase 6 Plan — Production API & Security Hardening

**版本**: 0.1 (DRAFT)
**日期**: 2026-04-09
**状态**: 待 Opus 4.6 审查
**前置条件**: REV-PROJECT-001 Approved

---

## 一、目标

将 AI-CFD Knowledge Harness 从 **CLI 工具** 升级为 **Production API Server**，具备：

1. **HTTP API** — 外部系统可以通过 REST API 调用知识编排功能
2. **数据加密** — 静态知识库和传输数据加密
3. **Notion Token 自动轮换** — 避免长期 token 过期导致的服务中断

---

## 二、待实现项

### 6.1 HTTP API Server

**现状**: Phase 5 仅支持 CLI 模式
**目标**: HTTP REST API，支持外部集成

#### 方案 A: FastAPI（推荐）
- 轻量级异步 API 框架
- 自动 OpenAPI 文档生成
- 支持 OAuth2/JWT 认证

#### 方案 B: Flask
- 更简单，但同步阻塞
- 需要手动文档

**关键端点**:

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/v1/pipeline/execute` | 执行 pipeline |
| POST | `/api/v1/spec/validate` | 验证 ReportSpec |
| GET | `/api/v1/knowledge/search` | 搜索知识库 |
| POST | `/api/v1/gates/check` | 运行 Gate 检查 |
| GET | `/api/v1/benchmarks/{id}` | 获取基准结果 |

**影响**: Phase 5 代码需要重构，增加 `knowledge_compiler/api/` 模块

#### Opus 4.6 审查点
1. API 设计是否合理？
2. 认证方案（OAuth2/JWT）是否足够？
3. 是否需要 rate limiting？

---

### 6.2 数据加密

**现状**: 知识库 JSON 文件明文存储
**目标**: AES-256-GCM 静态加密

#### 实现方案

```python
from cryptography.hazmat.primitives.ciphers.aead import AESCCM

class EncryptedKnowledgeStore:
    def __init__(self, key: bytes):
        self.aead = AESCCM(key, tag_length=16)

    def store(self, key: str, data: bytes) -> None:
        nonce = os.urandom(12)
        ct = self.aead.encrypt(nonce, data, None)
        # Store: nonce || ct

    def retrieve(self, key: str) -> bytes:
        # Read and decrypt
        nonce, ct = stored[:12], stored[12:]
        return self.aead.decrypt(nonce, ct, None)
```

**Key Management**: 使用 `.env` 或 AWS KMS（Phase 6 建议 AWS KMS，简化方案用 env）

**影响**: 新增 `knowledge_compiler/security/encryption.py`

#### Opus 4.6 审查点
1. AES-256-GCM 算法选择是否合理？
2. Key rotation 策略？
3. 是否需要 HSM？

---

### 6.3 Notion API Token 轮换

**现状**: 单一长期 token，无过期管理
**目标**: 自动轮换 + 多 token 容灾

#### 实现方案

```python
class RotatingNotionClient:
    def __init__(self, tokens: List[str]):
        self._tokens = tokens
        self._current = 0
        self._last_rotation = datetime.now()

    def rotate_if_needed(self):
        """检查 token 过期前 7 天自动轮换"""
        # 从 Notion 设置获取新 token
        # 更新当前 token
        # 保留旧 token 作为 fallback
```

**依赖**: Notion API token 管理策略

#### Opus 4.6 审查点
1. Token 轮换触发条件（7 天提前量是否合理）？
2. 多 token fallback 策略？

---

## 三、架构影响评估

| 项目 | 影响 | 评估 |
|------|------|------|
| 新增 `api/` 模块 | 中 | FastAPI 路由，不影响现有逻辑 |
| 新增 `security/encryption.py` | 中 | 新增模块，无破坏性 |
| 修改 `notion_cfd_loop.py` | 高 | Token 管理影响 SSOT 集成 |
| 新增依赖 (fastapi, cryptography) | 低 | requirements.txt 更新 |

---

## 四、开发顺序

```
Phase 6.1 → Phase 6.2 → Phase 6.3
HTTP API    →  数据加密 → Token 轮换
(P2)        (P2)      (P1)
```

**推荐顺序**: 6.3 (Token) → 6.2 (加密) → 6.1 (API)
**理由**: Token 轮换风险最低，API 架构影响最大

---

## 五、验收标准

- [ ] HTTP API 可处理外部请求（Phase 6.1）
- [ ] 知识库 JSON 文件加密存储（Phase 6.2）
- [ ] Token 自动轮换，零停机（Phase 6.3）
- [ ] 所有 Phase 6 测试通过
- [ ] Opus 4.6 架构审查通过

---

## 六、模型分工

| 任务 | Primary | Secondary |
|------|----------|-----------|
| FastAPI 实现 | Codex | GLM-5.1 |
| JWT/OAuth2 | GLM-5.1 | Opus 4.6 安全审查 |
| 加密模块 | Codex | GLM-5.1 |
| Token 轮换 | Codex | GLM-5.1 |
| 测试 | GLM-5.1 | MiniMax-M2.7 |
| 安全审查 | Opus 4.6 | — |

---

## 七、风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| API 破坏现有 CLI | 中 | 并行开发，CLI 保持兼容 |
| 加密 key 丢失 | 高 | 3-2-1 备份策略 |
| Token 轮换导致 SSOT 中断 | 高 | 新旧 token 并行 7 天窗口 |

---

**请 Opus 4.6 审查此 Phase 6 规划草案。**

审查后如同意架构方向，将开始 Phase 6.3（Token 轮换）实施。
