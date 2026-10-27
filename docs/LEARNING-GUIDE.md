# DailySpend 学习指南

这份文档不是 README 的复述，而是**带你读懂这套代码**的路线图：先建立整体印象，再按「一次请求经过哪些代码」的顺序拆解，最后给你可以动手改的练习题。

读完你应该能回答：

- 一个 `POST /api/transactions` 从进 Flask 到落库，中间经过哪几层、每层负责什么？
- 为什么金额要存「整数分」而不是 `DECIMAL`？
- CSRF token 在前端和后端分别是怎么配合的？为什么登录后必须换一个？
- 统计为什么不在 SQL 里用 `strftime`？那月度对比怎么算出来的？
- 新增一张表、一个接口、一个页面，分别要改哪些文件？

---

## 0. 三条阅读路径

| 你有多少时间 | 建议路线 |
| --- | --- |
| **30 分钟** | 读完 §1–§4，把项目跑起来，点一遍六个页面，再看 §3 的请求时序表 |
| **半天** | 加读 §5（数据模型）、§6.5（路由层五种模式）、§7（认证与安全）、§12（测试） |
| **想动手** | 精读 §8–§11，然后做 §14 的六道练习，每题都标了「改哪些文件 + 怎么验证」 |

---

## 1. 项目是什么

一个自用的个人记账网站：记录每天花了多少钱、花在哪里，并用图表回答「这个月的钱去哪了」。

功能上它已经超出「记账玩具」：多用户、会话安全、账单导入、预算超支、回收站、数据导出、Oracle 可移植。

| 层 | 选型 | 版本（实测） |
| --- | --- | --- |
| 后端 | Flask + Flask-SQLAlchemy + Flask-Migrate + Flask-Login + Flask-WTF | Flask 3.1 / SQLAlchemy 2.1 |
| 校验 | pydantic v2 | 2.14 |
| 数据库 | 开发 SQLite，生产可切 Oracle 23ai Free | — |
| 前端 | Vue 3 + Vite + TypeScript + Pinia + Vue Router + Naive UI + ECharts | Vue 3.5 / Vite 8 |
| 测试 | pytest + 无头 Edge 截图 | pytest 8.4 |

规模参考（方便你判断从哪读）：后端 `app` 包 30 个 Python 文件，最大的是 `services/imports.py`（436 行）、`models.py`（236 行）、`api/transactions.py`（213 行）；前端 19 个源文件，最大的是 `views/DashboardView.vue`（472 行）。

---

## 2. 5 分钟跑起来

```powershell
cd D:\deepseek\deepseekharnessPro\DailySpend
Set-ExecutionPolicy -Scope Process Bypass   # 只影响当前窗口
.\scripts\serve.ps1                          # http://127.0.0.1:8000
```

打开页面 → 注册（第一个账号会自动带默认分类和账户）→ 记一笔 → 看概览。

三个端口各管什么：

| 端口 | 谁在监听 | 什么时候用 |
| --- | --- | --- |
| 8000 | waitress，Flask 同时托管 API + 已构建的前端 | 日常使用 |
| 5000 | Flask 开发服务器 | 改后端代码（`--debug` 自动重载） |
| 5173 | Vite dev server | 改前端代码（热更新） |

开发模式要两个窗口：`scripts\dev.ps1 -m flask --app wsgi:app run --port 5000 --debug` 和 `scripts\build-frontend.ps1 -Dev`。

---

## 3. 全景：一次「记一笔」经过哪些代码

先记住这条链路，后面每个章节都是它的放大版。

```
浏览器（TransactionDialog.vue）
  │  POST /api/transactions   {amount:"12.34", category_id:3, ...}
  │  请求头 X-CSRFToken: xxx
  ▼
Vue 拦截器（api/client.ts）
  │  非 GET 请求自动带 CSRF token；失败自动续签重试一次
  ▼
Flask 路由（api/transactions.py: create_transaction）
  │  ① @login_required        → 没登录直接 401 JSON
  │  ② parse_payload()        → pydantic 校验金额/日期/长度，失败 422
  │  ③ get_category()         → 分类是否存在、是不是当前用户的（否则 404）
  │  ④ get_account()          → 账户同上
  │  ⑤ 推导 direction         → 分类是收入类就记 "in"，否则 "out"
  ▼
模型层（models.py: Transaction）
  │  amount 用 to_cents() 转成整数分；biz_date/occurred_at 补默认值
  ▼
SQLAlchemy → SQLite/Oracle
  │  db.session.add() + commit()；唯一键冲突 → 409
  ▼
响应 jsonify({"transaction": txn.to_dict()}) → 前端刷新列表
```

把这条链路里的每一层对上文件：

| 环节 | 文件 | 关键符号 |
| --- | --- | --- |
| 前端表单 | `frontend/src/components/TransactionDialog.vue` | `submit()` |
| HTTP 客户端 | `frontend/src/api/client.ts` | `http`、拦截器 |
| 接口封装 | `frontend/src/api/index.ts` | `transactionsApi` |
| 蓝图注册 | `backend/app/api/__init__.py` | `api_bp.register_blueprint` |
| 路由 | `backend/app/api/transactions.py` | `create_transaction`、`_conditions` |
| 校验 | `backend/app/schemas.py` | `TransactionCreate`、`parse_payload` |
| 归属校验 | `backend/app/api/helpers.py` | `get_category`、`get_account`、`commit` |
| 模型 | `backend/app/models.py` | `Transaction`、`to_dict` |
| 金额 | `backend/app/money.py` | `to_cents`、`from_cents` |
| 错误 | `backend/app/errors.py` + `errors_types.py` | `ApiError` 系列 |

---

## 4. 目录地图

### 后端 `backend/`

| 文件 | 职责 | 为什么值得读 |
| --- | --- | --- |
| `wsgi.py` | WSGI 入口，`app = create_app()` | 4 行，但解释了「为什么能被 waitress 直接跑」 |
| `app/__init__.py` | 应用工厂 `create_app()` | **全项目入口**，配置、扩展、蓝图、错误处理、CLI 都在这里装配 |
| `app/config.py` | `Settings`（pydantic-settings，`DS_*`） | 配置来源单一化；`resolve_database_url()` 处理相对 SQLite 路径 |
| `app/extensions.py` | `db`/`migrate`/`login_manager`/`csrf` 单例 | 为什么单例而不是 import app：避免循环依赖 |
| `app/db.py` | 连接钩子、引擎参数、健康探测 | SQLite `PRAGMA`、Oracle NLS、连接池差异都在这里 |
| `app/models.py` | 5 张表 + `to_dict()` | 数据模型的「唯一事实来源」 |
| `app/schemas.py` | 请求校验 | pydantic v2 的实战用法：`AmountIn`、月份归一化 |
| `app/money.py` | 元 ↔ 分 | 13 行，但涉及精度决策 |
| `app/utils/time.py` | 本地时区、月份运算 | 为什么全项目用「本地 naive 时间」 |
| `app/errors.py` / `errors_types.py` | 统一 JSON 错误 | 异常 → HTTP 状态码的映射规则 |
| `app/web.py` | 托管前端 `dist` | 同源部署 = 不需要 CORS |
| `app/cli.py` | `flask init-db` / `flask user create` | 运维入口 |
| `app/api/*.py` | 9 个蓝图、35 个接口 | 业务主体 |
| `app/services/*.py` | 统计、导入、预算、限流、种子数据 | 业务里「不好写在路由里」的部分 |
| `migrations/` | Alembic 迁移（3 个版本） | 数据库演进方式 |
| `tests/` | 17 个文件、136 个用例 | 见 §12 |

### 前端 `frontend/src/`

| 文件 | 职责 |
| --- | --- |
| `main.ts` / `App.vue` | 启动链、Naive UI 三个 Provider（message/dialog/notification） |
| `router/index.ts` | 路由表 + 登录守卫 |
| `stores/auth.ts` | 当前用户、`loadSession/login/logout` |
| `api/client.ts` | axios 实例：CSRF 注入、401 事件、错误文案归一 |
| `api/index.ts` | 按资源分组的接口函数（`transactionsApi` 等） |
| `types.ts` | **手写的 API 契约**（与后端 `to_dict()` 一一对应） |
| `layouts/AppLayout.vue` | 顶栏、导航、用户菜单 |
| `views/*.vue` | 七个页面 |
| `components/TransactionDialog.vue` | 记账弹窗（新增/编辑复用） |
| `components/BaseChart.vue` | ECharts 封装（init/setOption/resize/dispose） |
| `utils/format.ts` | 金额、日期、月份区间工具 |

### 其他

| 路径 | 说明 |
| --- | --- |
| `scripts/dev.ps1` | 带 `PYTHONPATH`/临时目录的运行器（也可直接 `python -m ...`） |
| `scripts/serve.ps1` / `build-frontend.ps1` | 生产启动、前端构建 |
| `scripts/e2e_smoke.py` | 端到端冒烟（真实 HTTP + 无头浏览器截图） |
| `scripts/oracle_*.py|ps1`、`setup-oracle.sql` | Oracle 相关工具链 |
| `docs/oracle-schema.sql` | 离线渲染的 Oracle 建表脚本 |
| `.pylibs/` `.tools/node/` `.devshim/` | 受限环境下的依赖/Node/临时目录垫片（见 §15） |

---

## 5. 数据模型

### 5.1 五张表

```
users ──┬── categories ──┬── transactions ──┬── (source: manual/wechat/alipay)
        │                │                  └── (external_id: 账单去重键)
        │                └── budgets (可指向分类，也可为 NULL=总预算)
        └── accounts ─────── transactions
```

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| `users` | `email`(唯一)、`password_hash`、`is_active` | 密码用 werkzeug 加盐哈希 |
| `categories` | `user_id`、`kind(expense/income)`、`icon`、`color` | 唯一键 `(user_id, kind, name)` |
| `accounts` | `user_id`、`type(cash/alipay/wechat/bank/credit/other)`、`initial_balance_cents` | 唯一键 `(user_id, name)` |
| `transactions` | `biz_date`、`occurred_at`、`amount_cents`、`direction`、`category_id`、`account_id`、`payee`、`note`、`source`、`external_id`、`deleted_at` | 唯一键 `(user_id, external_id)` |
| `budgets` | `month`(当月 1 号)、`category_id`(可空)、`amount_cents` | 唯一键 `(user_id, month, category_id)` |

### 5.2 六个关键决策（面试常问「为什么」）

**① 金额存整数分，不存浮点**

`amount_cents = 1234` 表示 12.34 元。理由：二进制浮点在 0.1+0.2 上就不准；而 SQLite 的 `DECIMAL` 实际存成浮点、Oracle 存成 `NUMBER`，两边往返行为不同。整数在两边都精确，聚合（`SUM`）也不会漂。

转换集中在 `money.py`：`to_cents()` 用 `ROUND_HALF_UP`，`from_cents()` 保证输出两位小数。

**② 时间用「本地 naive 时间」**

`utils/time.py: now_local()` 取 `Asia/Shanghai` 的当前时间并去掉 tzinfo。理由：个人记账以「我这边几号」为准，带时区反而让「本月」的边界更绕；中国无夏令时，风险很低。

`biz_date`（哪天）和 `occurred_at`（具体时刻）分开存：按天聚合只查 `biz_date`，走索引；`occurred_at` 留给未来做「时间分布」分析。

**③ 软删除 + 回收站**

删除只写 `deleted_at`，所有查询带 `deleted_at IS NULL`。好处：误删可救。代价：每个查询都要记得加条件——这也是为什么条件集中在 `transactions.py: _conditions()` 与 `services/stats.py: _conditions()` 两个地方。

**④ 账单去重键 `external_id`**

唯一键是 `(user_id, external_id)`，没有 `external_id` 的手工流水该列为 `NULL`。SQLite 和 Oracle 都允许唯一键里出现多个 `NULL`，所以手工记录不受影响。导入时优先用账单自带交易单号，没有就用 `sha1(日期+金额+收支+对方)` 生成 `wechat:xxxx` 形式的合成键。

**⑤ 索引按查询pattern建**

```python
Index("ix_txn_user_date", "user_id", "biz_date")
Index("ix_txn_user_category_date", "user_id", "category_id", "biz_date")
```

列表页默认按 `biz_date` 排序+区间过滤，统计按分类分组——这两条索引正好覆盖。注意名字都 ≤30 字符（老 Oracle 的标识符上限）。

**⑥ 布尔字段用 `Boolean`**

Oracle 23ai 有原生 `BOOLEAN`，SQLite 用整数 0/1，SQLAlchemy 自动翻译。不要手写 `IntEnum` 之类的模拟。

---

## 6. 后端分层

### 6.1 应用工厂 `create_app()`

`app/__init__.py` 是理解后端的钥匙，它按顺序做 8 件事：

1. `get_settings()` 读 `DS_*` 环境变量（`.env` 可选）
2. 建 `instance/` 目录、设置 Oracle 驱动默认值（`fetch_lobs=False`）
3. `app.config.update(...)`：密钥、数据库 URL、会话 Cookie 属性、CSRF、引擎参数
4. `db.init_app / migrate.init_app / csrf.init_app / login_manager.init_app`
5. 注册 `login_manager` 的 401 处理与 `user_loader`
6. 注册 API 蓝图（`/api` 前缀）
7. 挂载前端 SPA（`SERVE_FRONTEND` 开关，测试里关掉）
8. 注册错误处理与 CLI 命令

> 关键点：**没有全局 `app` 对象**。测试可以造 N 个 app（不同数据库 URL），互不干扰。

### 6.2 配置 `config.py`

`Settings` 用 pydantic-settings，字段名 `database_url` 对应环境变量 `DS_DATABASE_URL`。`resolve_database_url()` 把相对的 `sqlite:///instance/x.sqlite3` 锚定到仓库根目录，避免「在哪个目录启动」影响数据库位置。

`db.py: engine_options()` 做方言分支：Oracle 加 `pool_recycle=1800`（防 `ORA-02396`）和固定连接池；SQLite 只留 `pool_pre_ping`（SQLite 不接受 pool_size 参数）。

### 6.3 模型层

用 SQLAlchemy 2.0 风格：`Mapped[int]` + `mapped_column()`，主键统一：

```python
id: Mapped[int] = mapped_column(Integer, Identity(always=False), primary_key=True)
```

`Identity()` 在 Oracle 渲染成 `GENERATED BY DEFAULT AS IDENTITY`，SQLite 直接忽略（它的 `INTEGER PRIMARY KEY` 本来就自增）。

每个模型都有 `to_dict()`，**它是 API 的出口**：前端 `types.ts` 与它一一对应。改字段时两边要一起改（§14 练习 1 就是练这个）。

`Transaction.category` / `.account` 用 `lazy="joined"`，列表查询一次 SQL 带出关联，避免 N+1。

### 6.4 校验层 `schemas.py`

pydantic v2 的三个实用点：

```python
# ① 复用带校验的类型
AmountIn = Annotated[Decimal, AfterValidator(_validate_amount)]   # >0、≤上限、最多两位小数

# ② 字段级归一化（月份接受 "2026-03" 或 "2026-03-18"，统一成当月 1 号）
@field_validator("month", mode="before")

# ③ 统一把 ValidationError 转成自定义异常
def parse_payload(model_type, payload):  # 失败 → ValidationFailed → 422
```

`parse_payload` / `parse_query` 这两个函数是所有路由的入口守卫，保证「校验失败一定返回 422 + 字段级明细」。

### 6.5 路由层：五种反复出现的模式

以 `api/transactions.py` 为主样本：

**模式 1｜鉴权**：`@login_required` + 未登录由 `login_manager.unauthorized_handler` 统一返回 401 JSON（不是重定向到登录页，因为这是 API）。

**模式 2｜归属校验**：任何带 id 的资源都要验证「属于当前用户」，否则 404（不是 403，避免暴露资源是否存在）：

```python
def get_category(category_id: int) -> Category:
    category = db.session.get(Category, category_id)
    if category is None or category.user_id != current_user_id():
        raise NotFound("分类不存在")
    return category
```

**模式 3｜筛选条件集中在 `_conditions()`**：列表查询、统计、导出共用同一套过滤语义，避免三处行为不一致。

**模式 4｜分页**：`page/page_size` 由 `TransactionQuery` 校验（`page_size ≤ 200`），响应统一 `{items,page,page_size,total,total_pages}`。

**模式 5｜服务端推导，而不是信任客户端**：`direction` 不出现在创建请求里——它由所选分类的 `kind` 推导。客户端无法制造「收入分类 + 支出方向」的矛盾数据。

其他路由都短得多（`budgets.py` 57 行、`exports.py` 51 行），因为它们把计算交给了 `services/`。

### 6.6 服务层

| 文件 | 入口函数 | 做什么 |
| --- | --- | --- |
| `services/stats.py` | `summary/daily/by_category/by_account/monthly/iter_export_rows` | 全部聚合逻辑 |
| `services/imports.py` | `parse_statement → plan_import → apply_import` | 账单解析与落库（三段式，见 §9） |
| `services/budgets.py` | `status/upsert` | 预算进度 |
| `services/throttle.py` | `AttemptLimiter` | 登录失败限流（内存） |
| `services/seed.py` | `bootstrap_new_user` | 新用户默认分类/账户 |

**为什么服务层要单独存在**：路由只管 HTTP（取参、鉴权、返回），统计/解析这类「纯逻辑 + 查库」能脱离请求上下文单测。`test_stats.py` 与 `test_imports.py` 就是这么测的。

### 6.7 错误处理

`errors_types.py` 定义了 `ApiError` 家族（`ValidationFailed`/`NotFound`/`Unauthorized`/`Forbidden`/`Conflict`），`errors.py` 注册处理器，最终响应形状统一：

```json
{"error": {"code": "conflict", "message": "该分类下还有 3 条流水，删除前请先转移它们",
           "details": [{"loc": ["amount"], "msg": "金额必须大于 0", "type": "value_error"}]}}
```

前端 `client.ts: messageOf()` 直接把这个结构翻成一句中文提示，所以页面里只需要 `message.error(messageOf(err))`。

---

## 7. 认证与安全（重点）

### 7.1 会话流程

```
① 页面加载 → GET /api/auth/csrf → {csrf_token}（同时下发 session cookie）
② 登录    → POST /api/auth/login {email,password}
            后端：限流检查 → check_password → session.clear() → login_user()
            前端：401 时清掉缓存的 csrf（会话被重置，旧 token 失效）
③ 后续请求 → Cookie 自动带 session；写操作额外带 X-CSRFToken
④ 退出    → POST /api/auth/logout → logout_user() + session.clear()
```

用 **Session Cookie 而不是 JWT**：前后端同源部署，Cookie 天然可用、`HttpOnly` 让 JS 拿不到；JWT 放 localStorage 反而多一个 XSS 风险面。

Cookie 属性：`HttpOnly`、`SameSite=Lax`、`Secure`（由 `DS_SESSION_COOKIE_SECURE` 控制，HTTPS 下开）。

### 7.2 CSRF 双端配合

后端：`CSRFProtect` 全局保护所有非安全方法；错误被映射成 `code=csrf_failed` 的 400。

前端（`api/client.ts`）做三件事：

1. 请求拦截器：非 GET 时自动附 `X-CSRFToken`（没有就先取一次）
2. 响应拦截器：登录/注册/登出成功后**清掉缓存的 token**（因为后端 `session.clear()` 让它失效了）
3. 收到 `csrf_failed` 时**自动续签并重试一次**（`_csrfRetried` 防死循环）

这就是「会话固定防护」的代价：`session.clear()` 更安全，但必须让前端知道 token 变了。

### 7.3 登录限流与恒定耗时

- `AttemptLimiter`：同一 `IP+邮箱` 15 分钟内失败 5 次 → 锁定 15 分钟，返回 429
- 邮箱不存在时也跑一遍 `check_password`（用预置的假哈希），让「用户不存在」和「密码错」耗时接近，避免账号枚举
- 两者对外都是同一句「邮箱或密码不正确」

### 7.4 密码

`werkzeug.security.generate_password_hash/check_password_hash`（默认 scrypt 加盐）。改密接口要求先验证旧密码。

### 7.5 公网上线清单

| 项 | 设置 |
| --- | --- |
| 密钥 | `DS_SECRET_KEY=<长随机串>` |
| Cookie | `DS_SESSION_COOKIE_SECURE=true`（必须有 HTTPS） |
| 注册 | `DS_REGISTRATION_ENABLED=false` + `flask user create` 手工建号 |
| 限流 | 多进程部署时把内存限流换 Redis |
| 反向代理 | 在 Nginx/Caddy 终止 TLS，转发到 127.0.0.1:8000 |

---

## 8. 统计是怎么算的

`services/stats.py` 是「为了让 SQL 在 SQLite 和 Oracle 上都能跑」写得最克制的地方：

**不用方言函数**。不写 `strftime('%Y-%m', biz_date)`（SQLite）或 `to_char(biz_date,'YYYY-MM')`（Oracle），而是：

```python
.select_from(Transaction)
.group_by(Transaction.biz_date, Transaction.direction)   # 只按日期列分组
```

**日趋势补空日**：数据库只返回有记录的日期，`daily()` 先在 Python 里铺满整个区间（默认上限 `MAX_DAILY_POINTS = 400` 天，超了报 422），再填值——这样前端画图不用处理缺口。

**月度对比**：`monthly()` 以「今天所在月」为锚点往前推 N 个月（默认 6，上限 36），把日粒度结果在 Python 里按月累加。多一次内存聚合，换来零方言依赖。

**金额一律走 `from_cents()`** 输出两位小数字符串，前端只负责展示。

**导出的一个坑**：`exports.py` 必须先把行**取出来**再进生成器，否则 Flask 拆掉请求上下文后 `current_user` 已经不可用（这个 bug 真出现过，测试 `test_exports.py` 就是守它的）。

---

## 9. 账单导入流水线

`services/imports.py` 是全项目最长的文件，核心是三段式：

```
parse_statement(raw)
  ├─ decode_statement()   编码嗅探：UTF-8 BOM → UTF-8 → GB18030
  ├─ _locate_header()     在前 N 行里找同时含「交易时间 / 收/支 / 金额」的表头
  │                        （微信账单前面有十几行账户信息与汇总，必须跳过）
  ├─ _detect_source()     有「交易分类」→ 支付宝；否则微信
  └─ _parse_row()         逐行：收支映射、跳过退款/失败/不计收支、
                          金额去 ¥ 与千分位、时间多格式解析、
                          合成 external_id
plan_import(user_id, raw)
  └─ _existing_external_ids()  批量查已存在的单号（400 个一批），文件内重复也算
apply_import(user_id, plan)
  ├─ _match_category()    支付宝「交易分类」→ 关键词规则 → 已有分类名（同 kind）
  ├─ _match_account()     支付方式文本 → 账户名匹配 → 按类型猜（零钱→微信、花呗→信用卡）
  └─ 逐行 insert，最后一次 commit
```

设计要点：

- **预览与提交调同一个接口**，靠 `dry_run` 区分，前端只需上传两次文件，服务端不用缓存中间状态
- **跳过要有理由**：被跳过的行会带行号和原因返回，用户在预览页能看到「第 15 行：状态为已全额退款」
- **幂等**靠数据库唯一键兜底，不依赖内存去重；重复导入返回 `imported=0, duplicates=5`

---

## 10. 预算

`services/budgets.py: status()` 返回两部分：总预算（`category_id IS NULL`）与分类预算列表，每项都带 `spent/remaining/percent/over`。

两个容易踩的点：

**① 唯一键遇 NULL**：`UNIQUE(user_id, month, category_id)` 在 `category_id` 为 NULL 时不做约束（SQLite/Oracle 都把 NULL 视作互不相等），所以「总预算」的重复检查必须写在 `upsert()` 里手工做。

**② 口径**：只算 `direction='out'` 且未软删除、且落在该月区间内的流水。收入不冲抵支出预算。

`percent ≥ 80` 前端变黄，`over=True` 变红并额外列出超支分类。

---

## 11. 前端

### 11.1 启动链

```
main.ts: createApp(App).use(pinia).use(router).mount('#app')
  └─ App.vue: NConfigProvider(中文/主题) → NNotificationProvider → NDialogProvider → NMessageProvider
       └─ <router-view/>
            └─ router 守卫：没加载过会话就先 GET /api/auth/me
                 ├─ 未登录 + 受保护路由 → 跳 /login?redirect=...
                 └─ 已登录 + 访问 /login → 跳首页
                 └─ AppLayout（顶栏 + 内容区）→ 具体页面
```

### 11.2 `api/client.ts`：一个文件里的三个机制

1. **CSRF 注入与续签**（见 §7.2）
2. **401 广播**：任何非 auth 接口返回 401，派发 `window` 事件 `auth:expired`；`App.vue` 监听后清空用户并跳登录页。这样 100 个接口不用各写一遍跳转逻辑
3. **错误文案归一**：`messageOf()` 把后端的 `{error:{message,details}}` 变成一句中文；`details` 里第一条字段错误会被拼进去

### 11.3 状态

`stores/auth.ts` 只存「当前用户 + 公开配置」，用 setup store 写法（`ref` + `computed` + 函数）。业务数据不放 store——每个页面自己 `ref` + 请求，简单直接。

### 11.4 页面结构

| 页面 | 关键点 |
| --- | --- |
| `DashboardView.vue` | 一个 `Promise.all` 同时取 dashboard 统计、最近 6 条流水、本月预算；图表用 `computed` 生成 ECharts option，数据变了自动重绘 |
| `TransactionsView.vue` | 表格列用 `h()` 渲染函数（带金额颜色、来源标签）；筛选变化 → 重置页码 → 请求；关键字输入 300ms 防抖 |
| `TransactionDialog.vue` | 新增与编辑复用同一个弹窗：传了 `transaction` 就是编辑模式；提交完整表单，后端 `PUT` 支持部分更新（`exclude_unset`） |
| `ImportView.vue` | 选文件 → 预览（统计 + 前 10 条 + 跳过原因）→ 确认导入 |
| `BudgetsView.vue` | 月份切换、总预算/分类预算进度条、超支标签 |
| `TrashView.vue` | 恢复 / 永久删除 / 清空 |
| `SettingsView.vue` | 分类与账户的增删改、CSV 导出、改密 |

图表封装在 `BaseChart.vue`：`echarts.init` → `setOption` → `ResizeObserver` 跟随容器 → `dispose()`。**用 `watch` + `setOption(option, true)`**（第二个参数 `true` 表示不合并，避免旧 series 残留）。

### 11.5 类型契约

`types.ts` 是手写的：它对应后端 `to_dict()` 的输出。没有代码生成，所以**改后端返回字段时必须同步这里**，否则 TS 检查会报「属性不存在」——这其实是好事，编译期就发现契约漂移。

---

## 12. 测试体系

### 12.1 六层测试（136 个用例）

| 层次 | 文件 | 数量 | 验证什么 |
| --- | --- | --- | --- |
| 认证/安全 | `test_auth.py` `test_security.py` | 12+3 | 注册登录、限流、CSRF、Cookie 属性 |
| CRUD 与越权 | `test_categories.py` `test_accounts.py` `test_transactions.py` `test_trash.py` | 10+6+17+7 | 每个资源「别人的数据拿不到」 |
| 聚合与导出 | `test_stats.py` `test_exports.py` | 9+4 | 数字对不对、CSV 有没有 BOM |
| 账单导入 | `test_imports.py` | 18 | 编码、表头、脏行、去重、跨用户 |
| 预算 | `test_budgets.py` | 14 | 进度、超支、月份隔离、级联删除 |
| 基础设施 | `test_health.py` `test_web.py` `test_migrations.py` `test_db_hooks.py` `test_oracle_dialect.py` `test_oracle_provisioning.py` | 3+3+3+3+8+6 | 应用装配、迁移与模型一致、方言 DDL、连接钩子、建用户脚本纯函数 |
| 实库（可选） | `test_oracle_live.py` | 10 | 真实 Oracle 上的全链路（无凭据时 skip） |

> 共 136 个用例：`pytest -q` 会显示 `126 passed, 10 skipped`。数量用 `pytest --collect-only -q` 核对，参数化会展开成多条（例如金额校验 1 个函数 → 4 条用例）。

### 12.2 fixtures 怎么用

`conftest.py` 提供了搭积木式的夹具：

```python
def test_list_filters(auth_client, user, expense_category, make_transaction):
    make_transaction(user, category=expense_category, amount="10.00", biz_date=date(2026, 1, 1))
    ...
```

| 夹具 | 含义 |
| --- | --- |
| `app` | 每个用例一个独立 SQLite 文件 + `create_all`，结束即销毁 |
| `client` / `auth_client` | 匿名 / 已登录的 test client |
| `user` / `other_user` | 两个用户，用于越权测试 |
| `expense_category` / `income_category` / `account` | 默认种子数据里的第一条 |
| `make_transaction` | 绕过 HTTP 直接插数据，测试聚合时省事 |

### 12.3 给新接口写测试的模板

```python
def test_new_endpoint_requires_login(client):
    assert client.get("/api/whatever").status_code == 401

def test_new_endpoint_returns_expected(auth_client):
    response = auth_client.get("/api/whatever")
    assert response.status_code == 200
    assert response.get_json()["items"] == []

def test_new_endpoint_hides_other_users_data(auth_client, other_user):
    # 用 other_user 造一条数据，断言当前用户看不到
    ...
```

### 12.4 端到端冒烟 `scripts/e2e_smoke.py`

它做四件事（32 项检查）：

1. 建临时库、种演示数据、把**真实应用**起在 5055 端口（API + 已构建的 SPA）
2. 按浏览器的方式走 HTTP：取 CSRF → 登录 → 建/改/删流水 → 导入账单两次（验幂等）→ 预算 → 回收站 → 导出 CSV → SPA 深链接回退
3. 用无头 Edge 打开**七个页面**并截图到 `.tmp/screenshots/`：白屏（打包或运行时错误）会判定失败
4. 全部断言打印 `PASS/FAIL`，失败即非零退出

这个脚本的价值：pytest 测不到「前端 bundle 能不能真的跑起来」，而它专门测这个。

---

## 13. 迁移与数据库可移植性

### 13.1 Alembic 工作流

```powershell
# 改完 models.py 后
scripts\dev.ps1 -m flask --app wsgi:app db migrate -m "add xxx"
scripts\dev.ps1 -m flask --app wsgi:app db upgrade
scripts\dev.ps1 -m flask --app wsgi:app db check     # 确认没有漏掉的差异
```

三个迁移版本：`ae576c74bf35`（初始 5 表）→ `b7c1f0a2d9e4`（加 `source`）→ `54431316564c`（加 `budgets`）。

`test_migrations.py` 守着两件事：空库能升到 head；模型与迁移无差异。所以「改了模型忘了迁移」会在 CI 就红。

### 13.2 Oracle 差异清单（代码里已处理）

| 差异 | 处理方式 | 守护测试 |
| --- | --- | --- |
| 自增主键 | `Identity()` → `GENERATED BY DEFAULT AS IDENTITY` | `test_oracle_dialect` |
| 中文按字节算长度 | `String(n)` → `VARCHAR2(n CHAR)`；会话再强制 `NLS_LENGTH_SEMANTICS=CHAR` | 同上 + `test_db_hooks` |
| 没有 `ON DELETE RESTRICT` | 外键只用 `CASCADE`/`SET NULL`，不写子句即等价 | 同上 |
| `''` 等于 NULL | API 层统一 `blank_to_none()` | 同上 |
| `Text` → CLOB 返回 LOB 句柄 | 启动时 `oracledb.defaults.fetch_lobs = False` | `test_db_hooks` |
| 标识符 30 字符上限 | 索引/约束名都压短 | `test_oracle_dialect` |
| 反引号/大小写 | 全部小写并被 SQLAlchemy 加引号，原生 SQL 必须写 `"transactions"` | 文档 |
| 空闲连接被掐 | Oracle 加 `pool_recycle=1800` | `test_db_hooks` |

`docs/oracle-schema.sql` 是迁移在 Oracle 方言下的离线渲染结果，可直接用 SQL*Plus 执行；`scripts/render-oracle-ddl.ps1` 重新生成，`test_oracle_dialect.py` 里有一条快照同步测试防止漂移。

---

## 14. 动手练习（每题都给验证方式）

> 建议按顺序做，每题都跑一次 `scripts\dev.ps1 -m pytest -q` 和 `scripts\build-frontend.ps1`。

### 练习 1｜给流水加「标签」（练全链路）

改动清单：

1. `models.py`：`Transaction` 加 `tags: Mapped[str | None] = mapped_column(String(120))`，并在 `to_dict()` 里输出
2. `backend\migrations\versions\`：`db migrate -m "add transaction tags"` 生成新迁移
3. `schemas.py`：`TransactionCreate/Update` 加 `tags` 字段（长度校验）
4. `api\transactions.py`：创建/更新时赋值；`_conditions()` 里加 `tags.ilike(f"%{q}%")` 之类的筛选
5. `frontend\src\types.ts`：`Transaction` 加 `tags: string | null`
6. `components\TransactionDialog.vue`：加一个输入框
7. `views\TransactionsView.vue`：列里展示标签
8. `tests\test_transactions.py`：加 2 条用例（能存能读、能筛选）
9. `scripts\render-oracle-ddl.ps1`：重新渲染 Oracle DDL（否则快照测试会红）

验证：`pytest -q` 全绿；页面能存能查。

### 练习 2｜新增「按账户的月度报表」接口

1. `services\stats.py` 加 `monthly_by_account(user_id, months)`（参照 `monthly()` 的写法）
2. `api\stats.py` 加 `GET /api/stats/monthly-by-account`
3. `tests\test_stats.py` 加用例
4. 前端在 `DashboardView.vue` 或新页面里加一张堆叠柱状图

### 练习 3｜加「本周」快捷区间

改动集中在 `frontend\src\utils\format.ts`（加 `thisWeekRange()`）与 `DashboardView.vue`、`TransactionsView.vue` 的预设按钮。纯前端，最快的正向反馈。

### 练习 4｜导出改成 Excel（多 sheet）

后端加依赖 `openpyxl`，新增 `GET /api/exports/transactions.xlsx`：流水明细 + 分类汇总两个 sheet。注意仍然要「先查完再生成」，不要在生成器里用 `current_user`。

### 练习 5｜定期账单（房租/订阅）

1. `models.py` 新表 `recurring_rules`（用户、分类、金额、账户、每月几号、是否启用、上次生成月份）
2. 服务层 `services\recurring.py`：`run_due_rules(user_id, today)` 生成缺失月份的流水（用 `external_id = f"recurring:{rule_id}:{yyyy-mm}"` 保证幂等）
3. 触发点：登录后调用，或 `flask recurring run` CLI + Windows 计划任务
4. 测试重点：同一个月重复执行只生成一条

### 练习 6｜把统计下推到 SQL（性能对照）

当前 `monthly()` 是把日粒度结果在 Python 里累加。试着用 `func.extract("month", ...)` 或方言分支（SQLite `strftime` / Oracle `to_char`）在 SQL 里做，然后用 1 万条假数据对比耗时。**结论大概率是「没必要」**——但这个实验会让你理解为什么原实现选择可移植性。

---

## 15. 调试手册

| 现象 | 排查路径 |
| --- | --- |
| 页面 404 / 白屏 | `frontend\dist` 是否存在；`serve.ps1` 启动日志里有没有 "Serving frontend build from" |
| 接口 401 | 会话过期；看浏览器 Cookie 有没有 `session`；前端应自动跳登录 |
| 接口 400 `csrf_failed` | 前端缓存了旧 token；正常会自动续签重试，若持续出现检查 `client.ts` |
| 接口 422 | 响应里 `error.details[0].loc/msg` 直接指出字段 |
| 接口 409 | 唯一键冲突或「分类下还有流水」，看 `message` 文案 |
| 想看真实 SQL | 在 `create_app()` 里临时加 `app.config["SQLALCHEMY_ECHO"] = True`（记得别提交），或直接 `scripts\dev.ps1 -m flask --app wsgi:app shell` 里手动跑 `db.session.execute(...)` |
| 迁移报「目标版本不存在」 | `instance` 里的库太旧/太新；`flask db current` 与 `flask db history` 对照 |
| PowerShell 禁止运行脚本 | `Set-ExecutionPolicy -Scope Process Bypass` |
| `pytest` 全绿但页面不对 | 跑 `scripts\dev.ps1 ..\scripts\e2e_smoke.py`，看截图 |

日志位置：开发模式直接打到终端；`waitress` 模式下也是终端输出（`logger.exception` 会带堆栈）。

---

## 16. 术语表

| 术语 | 在这套代码里的含义 |
| --- | --- |
| 蓝图（Blueprint） | Flask 的路由分组单位，本项目一个资源一个蓝图 |
| 应用工厂 | `create_app()`，返回 Flask 实例，测试可造多个 |
| 软删除 | 只写 `deleted_at`，查询过滤；回收站可恢复 |
| 种子数据 | 新用户注册时自动创建的分类/账户（`services/seed.py`） |
| 账单（statement） | 微信/支付宝导出的 CSV 明细文件 |
| 去重键 | `external_id`，账单里的交易单号或其哈希 |
| 方言（dialect） | SQLAlchemy 对具体数据库的适配层，如 `oracle`、`sqlite` |
| 离线渲染 | Alembic `--sql` 模式，不连库只生成 DDL |
| 幂等 | 同样输入重复执行，结果不变（导入不重复记账） |
| 恒定耗时 | 用户不存在与密码错误耗时接近，防账号枚举 |

---

## 17. 附录：接口总表

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查（含数据库探测） |
| GET | `/api/auth/csrf` | 取 CSRF token |
| GET | `/api/auth/me` | 当前用户 + 公开配置 |
| POST | `/api/auth/register` | 注册（可被配置关闭） |
| POST | `/api/auth/login` | 登录（含限流） |
| POST | `/api/auth/logout` | 登出 |
| POST | `/api/auth/password` | 改密（校验旧密码） |
| GET/POST | `/api/categories` | 分类列表/新建 |
| PUT/DELETE | `/api/categories/<id>` | 改名/删除（有流水则 409） |
| GET/POST | `/api/accounts` | 账户列表/新建 |
| PUT/DELETE | `/api/accounts/<id>` | 修改/删除（有流水则 409） |
| GET | `/api/transactions` | 列表（区间/分类/账户/收支/来源/关键字/排序/分页） |
| GET/PUT/DELETE | `/api/transactions/<id>` | 详情/部分更新/软删除 |
| GET | `/api/transactions/trash` | 回收站列表 |
| POST | `/api/transactions/<id>/restore` | 恢复 |
| DELETE | `/api/transactions/<id>/purge` | 永久删除 |
| POST | `/api/transactions/trash/empty` | 清空回收站 |
| POST | `/api/imports/csv` | 账单导入（`dry_run` 预览/提交） |
| GET | `/api/stats/summary` | 区间汇总 |
| GET | `/api/stats/daily` | 日趋势（补空日） |
| GET | `/api/stats/by-category` | 分类占比 |
| GET | `/api/stats/by-account` | 账户占比 |
| GET | `/api/stats/monthly` | 近 N 月对比 |
| GET | `/api/stats/dashboard` | 上面五项的聚合（首屏一次拿全） |
| GET | `/api/budgets` | 某月预算进度 |
| PUT | `/api/budgets` | 设置/更新预算（按 month+category upsert） |
| DELETE | `/api/budgets/<id>` | 删除预算 |
| GET | `/api/exports/transactions.csv` | CSV 导出（带 BOM） |

---

有问题就对着 §3 的时序表找文件，对着 §12.3 的模板写测试，对着 §14 改代码——这三件事覆盖了日常开发的 90%。
