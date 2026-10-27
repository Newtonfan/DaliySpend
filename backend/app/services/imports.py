"""Import WeChat Pay / Alipay statement exports.

Both products export CSV files that start with a block of account metadata,
followed by a header row and the actual transactions.  The column names differ
between the two, so this module normalises a small set of aliases instead of
hard-coding one vendor format:

==================  ==========================  ==========================
字段                WeChat                      Alipay
==================  ==========================  ==========================
时间                交易时间                    交易时间
对方                交易对方                    交易对方
说明                商品                        商品说明
收支                收/支                       收/支
金额                金额(元)                    金额
状态                当前状态                    交易状态
单号                交易单号                    交易订单号
分类（仅支付宝）    —                           交易分类
==================  ==========================  ==========================

The importer is idempotent: every row gets a stable ``external_id`` (the
statement's own transaction id, or a hash of the row when the vendor omits it)
and ``transactions`` has a ``(user_id, external_id)`` unique constraint, so
re-importing an overlapping date range never duplicates money.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Iterable, Sequence

from sqlalchemy import select

from ..errors_types import ApiError
from ..extensions import db
from ..models import Account, Category, Transaction
from ..money import to_cents

ENCODINGS = ("utf-8-sig", "utf-8", "gb18030")

MAX_ROWS = 5000
MAX_BYTES = 10 * 1024 * 1024

#: Column aliases; keys are the canonical field names used below.
ALIASES: dict[str, tuple[str, ...]] = {
    "time": ("交易时间", "交易创建时间", "创建时间", "付款时间"),
    "payee": ("交易对方", "对方名称", "对方"),
    "product": ("商品", "商品说明", "商品名称", "商品描述"),
    "direction": ("收/支", "收支", "收支类型"),
    "amount": ("金额(元)", "金额（元）", "金额"),
    "method": ("支付方式", "收/付款方式", "付款方式"),
    "status": ("当前状态", "交易状态"),
    "external": ("交易单号", "交易订单号", "订单号"),
    "category": ("交易分类", "分类"),
    "note": ("备注",),
}

REQUIRED_TOKENS = ("交易时间", "金额", "收/支")

#: Statuses that must not be booked as spending.
SKIP_STATUS_KEYWORDS = ("退款", "失败", "关闭", "撤销", "取消")

TIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M",
    "%Y-%m-%d",
    "%Y/%m/%d",
)

AMOUNT_JUNK = re.compile(r"[^\d.\-]")

#: Alipay transaction categories -> one of the app's default category names.
CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("餐饮", ("餐饮", "美食", "快餐", "咖啡", "外卖", "食品", "生鲜", "零食")),
    ("交通", ("交通", "出行", "打车", "地铁", "公交", "加油", "停车", "机票", "火车")),
    ("购物", ("购物", "百货", "服饰", "数码", "超市", "电商", "日用", "家居")),
    ("居住", ("住房", "物业", "房租", "水电", "缴费", "燃气", "宽带")),
    ("娱乐", ("文化", "休闲", "娱乐", "电影", "游戏", "旅游", "酒店")),
    ("医疗", ("医疗", "健康", "药店", "医院", "体检")),
    ("学习", ("教育", "培训", "图书", "学习", "办公")),
    ("通讯", ("通讯", "物流", "话费", "快递", "流量")),
    ("人情", ("转账", "红包", "人情", "礼金")),
    ("工资", ("工资", "薪资", "薪酬", "奖金")),
)


@dataclass(frozen=True)
class SkippedRow:
    line: int
    reason: str


@dataclass(frozen=True)
class ParsedRow:
    line: int
    source: str
    biz_date: date
    occurred_at: datetime
    amount_cents: int
    direction: str
    payee: str | None
    note: str | None
    external_id: str
    category_hint: str | None = None
    method: str | None = None

    def to_dict(self) -> dict:
        return {
            "line": self.line,
            "date": self.biz_date.isoformat(),
            "amount": f"{Decimal(self.amount_cents) / 100:.2f}",
            "direction": self.direction,
            "payee": self.payee,
            "note": self.note,
            "category_hint": self.category_hint,
            "method": self.method,
            "external_id": self.external_id,
        }


@dataclass
class ParsedStatement:
    source: str
    encoding: str
    total_rows: int
    rows: list[ParsedRow] = field(default_factory=list)
    skipped: list[SkippedRow] = field(default_factory=list)


@dataclass
class ImportPlan:
    statement: ParsedStatement
    new_rows: list[ParsedRow]
    duplicates: list[ParsedRow]

    @property
    def totals(self) -> dict:
        expense = sum(row.amount_cents for row in self.new_rows if row.direction == "out")
        income = sum(row.amount_cents for row in self.new_rows if row.direction == "in")
        return {"expense": _money(expense), "income": _money(income)}

    @property
    def date_range(self) -> dict | None:
        if not self.new_rows:
            return None
        dates = [row.biz_date for row in self.new_rows]
        return {"from": min(dates).isoformat(), "to": max(dates).isoformat()}


def _money(cents: int) -> str:
    return f"{Decimal(cents) / 100:.2f}"


# --------------------------------------------------------------------- decoding


def decode_statement(raw: bytes) -> tuple[str, str]:
    """Decode an uploaded statement, returning ``(text, encoding)``."""
    candidates = ("utf-8-sig",) if raw.startswith(b"\xef\xbb\xbf") else ENCODINGS[1:]
    for encoding in candidates:
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise ApiError(
        "无法识别文件编码，请导出为 UTF-8 或 GBK 的 CSV",
        code="unsupported_encoding",
        status=422,
    )


# ----------------------------------------------------------------------- parsing


def _normalise(cell: str) -> str:
    return (cell or "").replace(" ", "").replace("\ufeff", "").strip()


def _locate_header(rows: Sequence[Sequence[str]]) -> tuple[int, dict[str, int], str]:
    for index, row in enumerate(rows):
        joined = ",".join(row)
        if all(token in joined for token in REQUIRED_TOKENS):
            header = [_normalise(cell) for cell in row]
            mapping: dict[str, int] = {}
            for key, aliases in ALIASES.items():
                for alias in aliases:
                    if _normalise(alias) in header:
                        mapping[key] = header.index(_normalise(alias))
                        break
            return index, mapping, joined
    raise ApiError(
        "无法识别账单格式：没有找到包含「交易时间 / 收/支 / 金额」的表头，"
        "请确认上传的是微信或支付宝导出的 CSV 明细",
        code="unrecognised_statement",
        status=422,
    )


def _detect_source(header_text: str) -> str:
    if "交易分类" in header_text or "收/付款方式" in header_text:
        return "alipay"
    if "支付方式" in header_text or "当前状态" in header_text:
        return "wechat"
    return "wechat"


def _cell(row: Sequence[str], mapping: dict[str, int], key: str) -> str:
    index = mapping.get(key)
    if index is None or index >= len(row):
        return ""
    return (row[index] or "").strip()


def _parse_time(raw: str) -> datetime | None:
    text = raw.strip()
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _parse_amount(raw: str) -> int:
    cleaned = AMOUNT_JUNK.sub("", raw or "")
    if not cleaned or cleaned in {"-", "."}:
        raise ValueError("金额为空")
    try:
        value = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"金额无法解析：{raw}") from exc
    if value <= 0:
        raise ValueError(f"金额必须大于 0：{raw}")
    return to_cents(value)


def _synthetic_external_id(row: ParsedRow) -> str:
    raw = "|".join(
        [
            row.source,
            row.biz_date.isoformat(),
            str(row.amount_cents),
            row.direction,
            row.payee or "",
            row.note or "",
        ]
    )
    return f"{row.source}:{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:24]}"


def _build_note(product: str, note: str) -> str | None:
    parts = [part.strip() for part in (product, note) if part and part.strip()]
    if not parts:
        return None
    return " / ".join(dict.fromkeys(parts))


def _parse_row(
    row: Sequence[str], mapping: dict[str, int], source: str, line: int
) -> ParsedRow | SkippedRow:
    direction_text = _cell(row, mapping, "direction")
    if direction_text not in ("支出", "收入"):
        return SkippedRow(line, f"收支类型为「{direction_text or '空'}」，不计入收支")

    status = _cell(row, mapping, "status")
    for keyword in SKIP_STATUS_KEYWORDS:
        if keyword in status:
            return SkippedRow(line, f"状态为「{status}」")

    occurred_at = _parse_time(_cell(row, mapping, "time"))
    if occurred_at is None:
        return SkippedRow(line, f"无法解析交易时间「{_cell(row, mapping, 'time')}」")

    try:
        amount_cents = _parse_amount(_cell(row, mapping, "amount"))
    except ValueError as exc:
        return SkippedRow(line, str(exc))

    payee = _cell(row, mapping, "payee") or None
    note = _build_note(_cell(row, mapping, "product"), _cell(row, mapping, "note"))

    parsed = ParsedRow(
        line=line,
        source=source,
        biz_date=occurred_at.date(),
        occurred_at=occurred_at,
        amount_cents=amount_cents,
        direction="out" if direction_text == "支出" else "in",
        payee=payee,
        note=note,
        external_id="",
        category_hint=_cell(row, mapping, "category") or None,
        method=_cell(row, mapping, "method") or None,
    )
    external = _cell(row, mapping, "external")
    return replace(parsed, external_id=external or _synthetic_external_id(parsed))


def parse_statement(raw: bytes) -> ParsedStatement:
    """Parse a statement file into rows plus per-line skip reasons."""
    text, encoding = decode_statement(raw)
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise ApiError("文件是空的", code="empty_statement", status=422)

    header_index, mapping, header_text = _locate_header(rows)
    if "amount" not in mapping:
        raise ApiError("表头里缺少金额列", code="unrecognised_statement", status=422)

    source = _detect_source(header_text)
    statement = ParsedStatement(source=source, encoding=encoding, total_rows=0)

    missing = [key for key in ("time", "direction", "amount") if key not in mapping]
    if missing:
        raise ApiError(
            f"表头缺少必要列：{', '.join(missing)}",
            code="unrecognised_statement",
            status=422,
        )

    for offset, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        if not row or not any((cell or "").strip() for cell in row):
            continue
        statement.total_rows += 1
        if statement.total_rows > MAX_ROWS:
            raise ApiError(
                f"单次最多导入 {MAX_ROWS} 行，请按月导出后再导入",
                code="statement_too_large",
                status=413,
            )
        result = _parse_row(row, mapping, source, offset)
        if isinstance(result, SkippedRow):
            statement.skipped.append(result)
        else:
            statement.rows.append(result)

    return statement


# ------------------------------------------------------------------ reconciliation


def _existing_external_ids(user_id: int, ids: Sequence[str]) -> set[str]:
    found: set[str] = set()
    for start in range(0, len(ids), 400):
        chunk = ids[start : start + 400]
        rows = db.session.scalars(
            select(Transaction.external_id).where(
                Transaction.user_id == user_id,
                Transaction.external_id.in_(chunk),
            )
        ).all()
        found.update(value for value in rows if value)
    return found


def plan_import(user_id: int, raw: bytes) -> ImportPlan:
    """Parse the file and split rows into "new" and "already imported"."""
    statement = parse_statement(raw)
    existing = _existing_external_ids(user_id, [row.external_id for row in statement.rows])

    new_rows: list[ParsedRow] = []
    duplicates: list[ParsedRow] = []
    seen: set[str] = set()
    for row in statement.rows:
        if row.external_id in existing or row.external_id in seen:
            duplicates.append(row)
            continue
        seen.add(row.external_id)
        new_rows.append(row)

    return ImportPlan(statement=statement, new_rows=new_rows, duplicates=duplicates)


def _match_category(
    hint: str | None, kind: str, categories: Sequence[Category]
) -> Category | None:
    candidates = [category for category in categories if category.kind == kind]
    if not candidates:
        return None
    by_name = {category.name: category for category in candidates}

    if hint:
        if hint in by_name:
            return by_name[hint]
        for name, category in by_name.items():
            if name in hint or hint in name:
                return category
        for target, keywords in CATEGORY_RULES:
            if any(keyword in hint for keyword in keywords) and target in by_name:
                return by_name[target]
    return None


def _match_account(method: str | None, accounts: Sequence[Account]) -> Account | None:
    if not method:
        return None
    for account in accounts:
        if account.name and (account.name in method or method in account.name):
            return account

    hints: tuple[tuple[tuple[str, ...], str], ...] = (
        (("零钱", "微信"), "wechat"),
        (("花呗", "借呗", "信用卡"), "credit"),
        (("支付宝", "余额宝", "余额"), "alipay"),
        (("银行卡", "储蓄卡", "借记卡", "银行"), "bank"),
        (("现金",), "cash"),
    )
    for keywords, account_type in hints:
        if any(keyword in method for keyword in keywords):
            for account in accounts:
                if account.type == account_type:
                    return account
    return None


def _fallback_category(kind: str, categories: Sequence[Category]) -> Category | None:
    """Last resort: prefer the "其他" bucket of the requested kind."""
    candidates = [category for category in categories if category.kind == kind]
    for category in candidates:
        if "其他" in category.name:
            return category
    return candidates[0] if candidates else None


def apply_import(
    user_id: int,
    plan: ImportPlan,
    *,
    default_category_id: int | None = None,
    default_account_id: int | None = None,
) -> int:
    """Persist the plan's new rows; returns how many were inserted."""
    categories = db.session.scalars(
        select(Category).where(Category.user_id == user_id)
    ).all()
    accounts = db.session.scalars(
        select(Account).where(Account.user_id == user_id)
    ).all()

    explicit_category = next(
        (category for category in categories if category.id == default_category_id), None
    )
    explicit_account = next(
        (account for account in accounts if account.id == default_account_id), None
    )

    inserted = 0
    for row in plan.new_rows:
        kind = "income" if row.direction == "in" else "expense"
        category = _match_category(row.category_hint, kind, categories)
        if category is None and explicit_category is not None and explicit_category.kind == kind:
            category = explicit_category
        if category is None:
            category = _fallback_category(kind, categories)
        if category is None:
            raise ApiError(
                "还没有可用分类，请先在「设置」里创建分类",
                code="no_category",
                status=409,
            )

        account = _match_account(row.method, accounts) or explicit_account

        db.session.add(
            Transaction(
                user_id=user_id,
                biz_date=row.biz_date,
                occurred_at=row.occurred_at,
                amount_cents=row.amount_cents,
                direction=row.direction,
                category_id=category.id,
                account_id=account.id if account else None,
                payee=row.payee,
                note=row.note,
                source=row.source,
                external_id=row.external_id,
            )
        )
        inserted += 1

    db.session.commit()
    return inserted


def _describe(plan: ImportPlan, imported: int | None = None) -> dict:
    statement = plan.statement
    return {
        "source": statement.source,
        "encoding": statement.encoding,
        "total_rows": statement.total_rows,
        "ready": len(plan.new_rows),
        "duplicates": len(plan.duplicates),
        "skipped": len(statement.skipped),
        "skipped_reasons": [
            {"line": skipped.line, "reason": skipped.reason}
            for skipped in statement.skipped[:20]
        ],
        "totals": plan.totals,
        "date_range": plan.date_range,
        "sample": [row.to_dict() for row in plan.new_rows[:10]],
        "imported": imported,
    }


def preview(user_id: int, raw: bytes) -> dict:
    return _describe(plan_import(user_id, raw))


def commit(
    user_id: int,
    raw: bytes,
    *,
    default_category_id: int | None = None,
    default_account_id: int | None = None,
) -> dict:
    plan = plan_import(user_id, raw)
    imported = apply_import(
        user_id,
        plan,
        default_category_id=default_category_id,
        default_account_id=default_account_id,
    )
    return _describe(plan, imported=imported)
