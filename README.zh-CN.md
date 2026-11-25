<div align="center">

# AI-Ready Semantic Hub

**为 BI 与 AI Agent 提供同一套可版本化的业务语义。**

[English](README.md) · [简体中文](README.zh-CN.md) · [架构设计](docs/ARCHITECTURE.md) · [语义规范](docs/SEMANTIC_SPEC.md) · [参与贡献](CONTRIBUTING.md)

![Version](https://img.shields.io/badge/version-0.1.0-087f70)
![Python](https://img.shields.io/badge/python-3.11%2B-3670a0)
![License](https://img.shields.io/badge/license-MIT-blue)

</div>

一个轻量的业务语义管理与服务中心：集中定义数据模型、指标口径、关联关系和业务术语，经过校验与发布后，通过 Web 工作台、REST API 和 MCP 向 BI 开发者及 AI Agent 提供一致、可追溯的语义契约。

**v0.1 是可运行的参考实现**，适合本地评估及小型可信团队试点。它尚不是分布式查询引擎、全自动 Text-to-SQL 产品或企业身份平台。演示不需要大模型 API Key 或数据库账号，附带数据定义均为合成示例。

## 项目定位

数据库元数据能告诉 Agent 有一个 `amount` 字段，却未必能解释它是买家实付、商家折后 GMV，还是结算收入；也不能天然回答哪些订单需要排除、按什么时区统计、表关联是否会放大金额。

Semantic Hub 将这些业务决策变成可以编辑、校验、评审和发布的**语义契约**。它位于数据仓库之上，为 BI 与 AI 提供共享的定义和接口。返回的 SQL 和上下文携带发布版本及内容哈希，便于复现与审计。

| 能力 | v0.1 已实现 |
| --- | --- |
| 数据模型 | 物理表、字段类型、责任人、复合主键与数据粒度 |
| 指标定义 | sum、count、去重计数、avg、min、max、总额比值、固定筛选 |
| 关联关系 | 复合关联键、基数声明；编译器支持直接多对一/一对一关联 |
| 业务含义 | 描述、中英文同义词、业务规则、标签、术语 |
| 版本治理 | 校验后保存草稿、管理员发布、不可变快照、恢复为新草稿、审计历史 |
| AI 接入 | 中英文词法检索、完整上下文包、三个只读 MCP 工具 |
| SQL 约束 | 标识符白名单、筛选值参数化、币种约束、拒绝歧义和可能放大的关联 |
| 权限 | viewer/editor/admin Token 角色、public/internal 实体可见性 |
| 可移植性 | YAML/JSON 导入导出、JSON Schema、保守的 dbt manifest 导入 |
| 开源工程 | Web 工作台、CLI、OpenAPI、Docker Compose、测试与 GitHub Actions |

## 快速启动

需要 Python 3.11+；本地验证环境为 Python 3.12。在仓库根目录执行：

```bash
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows PowerShell 则执行：.venv\Scripts\Activate.ps1
python -m pip install -e ".[mcp]"
semantic-hub serve --demo
```

访问 [http://127.0.0.1:8000](http://127.0.0.1:8000)，接口文档位于 `/docs`。

演示模式明确关闭认证并给予本地管理员权限，CLI 默认只绑定本机回环地址。新数据库初始化三个电商模型、四个指标、一条复合关联和两个术语；重启不会覆盖已有数据。如需重置，停止服务后指定另一个 `--db` 路径。

使用仓库锁定的依赖版本：

```bash
uv sync --frozen --extra mcp --extra dev
uv run semantic-hub serve --demo
```

也可使用 Docker：

```bash
docker compose up --build
```

Compose 的主机端口只绑定 `127.0.0.1`，使用持久卷和非 root 容器用户。团队使用前请按 [部署说明](docs/DEPLOYMENT.md) 配置 Token 和访问入口。

## 体验完整闭环

1. **Semantic catalog**：搜索 `GMV` 或 `成交额`，查看口径、固定筛选和业务规则。
2. **Relationships**：检查 `platform + shop_id` 两列关联，理解为什么不能只使用店铺 ID。
3. **Query playground**：加载电商查询示例并编译，分别查看 SQL、参数和依赖关系。
4. **Definition editor**：修改 YAML、校验、填写变更说明并保存草稿；Agent 此时仍读取已发布版本。
5. **Publish**：管理员发布指定草稿版本，历史快照保持不变。
6. **Agent context**：输入 `按地区统计商家折后 GMV`，检查返回给 Agent 的定义、关联与版本哈希。
7. **Version history**：把历史版本恢复为新草稿，重新审核后再发布。

当前界面以英文为主，定义内容、检索和项目文档支持中文；完整界面国际化列入后续计划。

## 语义定义示例

指标引用明确字段，不接受任意可执行 SQL：

```yaml
id: seller_gmv
label: Seller GMV / 商家折后 GMV
owner: commerce-analytics
model: order_items
aggregation: sum
column: seller_net_amount
unit: currency
currency_dimension: order_items.currency
time_dimension: order_items.order_date
filters:
  - {field: order_items.status, op: ne, value: cancelled}
  - {field: order_items.is_sample, op: eq, value: false}
business_rules:
  - 不含运费和税费；必须按币种分组，或限定单一币种。
```

以上是指标片段，完整可校验目录见 [examples/commerce.yaml](examples/commerce.yaml)。`business_rules` 是提供给人和 Agent 的说明；只有 `filters`、`currency_dimension` 等结构化字段会影响 SQL 编译。物理数据唯一性、时区预处理等仍需数仓层保障。

```bash
semantic-hub validate examples/commerce.yaml
semantic-hub schema > catalog.schema.json
semantic-hub import-dbt manifest.json > imported.yaml
```

dbt 导入要求显式字段元数据和 `meta.semantic_hub.primary_key`。缺少信息的模型会被跳过并打印原因，不会猜测主键、指标或关系。详见 [集成说明](docs/INTEGRATIONS.md)。

## REST 与 SQL 编译

演示模式不需要认证。启用认证后增加 `Authorization: Bearer <token>`。

```bash
curl -X POST http://127.0.0.1:8000/api/compile \
  -H 'Content-Type: application/json' \
  --data-binary @examples/query.json
```

返回 `sql`、`parameters`、`lineage`、`dialect`、`revision`、`digest`、`warnings`。PostgreSQL/Hologres 使用 psycopg 风格命名参数，DuckDB 使用 `$name` 参数；交给执行层时必须分别传递 SQL 与参数，禁止直接字符串拼接。

**本项目不执行数仓 SQL。** Hologres 是基于 PostgreSQL 兼容语法的编译目标，目前没有声称通过真实 Hologres/PostgreSQL 联调或性能认证。v0.1 不支持跨事实表查询、多跳关联、任意公式、汇率换算或时间粒度转换。

## MCP 接入

安装 `mcp` 可选依赖并保持 API 服务运行，在支持 stdio 的 MCP 客户端中配置：

```json
{
  "mcpServers": {
    "semantic-hub": {
      "command": "/absolute/path/to/.venv/bin/semantic-hub",
      "args": ["mcp"],
      "env": {
        "HUB_URL": "http://127.0.0.1:8000",
        "HUB_TOKEN": "your-viewer-token"
      }
    }
  }
}
```

Windows 使用 `.venv\\Scripts\\semantic-hub.exe` 的完整路径。本地演示可省略 `HUB_TOKEN`；真实 Token 应保存在客户端密钥配置或进程环境，不要提交到仓库。

| 工具 | 用途 |
| --- | --- |
| `search_semantics` | 检索已发布模型、指标及术语 |
| `get_semantic_context` | 获取经过权限过滤的定义及直接关联上下文 |
| `compile_metric_query` | 将结构化指标请求编译为参数化 SQL |

适配器使用官方 MCP SDK 仍维护的 **v1 系列**，显式限定 `mcp>=1.28,<2`，当前仅提供 stdio，并复用 REST API 的权限规则。不提供修改语义或执行 SQL 的 MCP 工具。[SDK v1 文档](https://py.sdk.modelcontextprotocol.io/v1/)。

## 框架结构

| 位置 | 职责 |
| --- | --- |
| `src/semantic_hub/models.py` | 类型化语义契约、JSON Schema |
| `validation.py` | 引用、类型、关联键及可见性校验 |
| `compiler.py` | 确定性的受约束 SQL 编译 |
| `retrieval.py` | 中英文词法检索及上下文组装 |
| `store.py` | SQLite 事务、快照版本与审计 |
| `api.py` | REST、认证授权及工作台服务 |
| `mcp_server.py` | 只读 MCP 到 REST 适配 |
| `importers.py`、`cli.py` | 元数据导入和开发命令 |
| `static/` | 无前端构建依赖的响应式工作台 |
| `tests/`、`scripts/browser_smoke.py` | 核心、API、MCP 和浏览器流程验证 |
| `docs/` | 详细架构、规范、部署、集成与路线图 |

## 开发与验证

```bash
python -m pip install -e ".[dev,mcp]"
python -m unittest discover -s tests -v
ruff check src tests scripts
ruff format --check src tests scripts
python -m build
```

MCP 集成测试会启动临时 HTTP 服务，使用真实 stdio 客户端验证协议握手、工具发现、调用和权限拒绝。SQL 语义测试在 SQLite 上执行通用 SQL 子集，仅调整参数占位符；这不能替代目标数仓兼容性测试。

浏览器流程测试需要独立的演示数据库：

```bash
python -m playwright install chromium
semantic-hub serve --demo --db .semantic-hub/browser-test.db
# 另开终端，使用相同虚拟环境：
python scripts/browser_smoke.py
```

参与贡献请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)、[SECURITY.md](SECURITY.md)、[路线图](docs/ROADMAP.md) 与 [CHANGELOG.md](CHANGELOG.md)。项目采用 MIT 许可证，不依赖私有运行时、外部行为分析或托管推理服务。

本地验证结果见 [VALIDATION.md](docs/VALIDATION.md)，推送到 GitHub 的步骤见 [PUBLISHING.md](docs/PUBLISHING.md)。
