"""Statement import tests (WeChat Pay / Alipay CSV)."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from app.extensions import db
from app.models import Account, Transaction

FIXTURES = Path(__file__).parent / "fixtures"

WECHAT = FIXTURES / "wechat_statement.csv"
ALIPAY = FIXTURES / "alipay_statement.csv"


def wechat_bytes() -> bytes:
    return WECHAT.read_bytes()


def alipay_text() -> str:
    return ALIPAY.read_text(encoding="utf-8")


def post_statement(client, raw: bytes, *, dry_run: bool = True, **form):
    data = {
        "file": (io.BytesIO(raw), "statement.csv"),
        "dry_run": "true" if dry_run else "false",
    }
    data.update({key: str(value) for key, value in form.items()})
    return client.post("/api/imports/csv", data=data, content_type="multipart/form-data")


def test_preview_recognises_wechat_statement(auth_client):
    response = post_statement(auth_client, wechat_bytes())
    assert response.status_code == 200
    payload = response.get_json()

    assert payload["source"] == "wechat"
    assert payload["encoding"] == "utf-8"
    assert payload["total_rows"] == 7
    # Refunded row and the "其他" (neutral) cash withdrawal are skipped.
    assert payload["skipped"] == 2
    assert payload["ready"] == 5
    assert payload["duplicates"] == 0
    assert payload["totals"] == {"expense": "231.90", "income": "8000.00"}
    assert payload["date_range"] == {"from": "2026-01-03", "to": "2026-01-25"}
    assert payload["imported"] is None


def test_preview_does_not_write(auth_client):
    post_statement(auth_client, wechat_bytes())
    assert db.session.query(Transaction).count() == 0


def test_commit_writes_rows_with_source_and_parsed_amounts(auth_client):
    response = post_statement(auth_client, wechat_bytes(), dry_run=False)
    assert response.status_code == 200
    assert response.get_json()["imported"] == 5

    transactions = db.session.query(Transaction).order_by(Transaction.biz_date).all()
    assert len(transactions) == 5
    assert {txn.source for txn in transactions} == {"wechat"}

    starbucks = next(txn for txn in transactions if txn.payee == "星巴克咖啡")
    assert starbucks.amount_cents == 3200  # ¥32.00
    assert starbucks.direction == "out"
    assert starbucks.note == "拿铁 / 早餐"

    salary = next(txn for txn in transactions if txn.direction == "in")
    assert salary.amount_cents == 800000  # ¥8,000.00 (thousand separator)
    assert salary.external_id == "T2007"


def test_reimport_is_idempotent(auth_client):
    first = post_statement(auth_client, wechat_bytes(), dry_run=False).get_json()
    assert first["imported"] == 5

    second = post_statement(auth_client, wechat_bytes(), dry_run=False).get_json()
    assert second["imported"] == 0
    assert second["duplicates"] == 5
    assert second["ready"] == 0
    assert db.session.query(Transaction).count() == 5


def test_soft_deleted_rows_still_block_reimport(auth_client):
    post_statement(auth_client, wechat_bytes(), dry_run=False)
    removed = db.session.query(Transaction).first()
    removed.deleted_at = removed.created_at
    db.session.commit()

    again = post_statement(auth_client, wechat_bytes(), dry_run=False).get_json()
    assert again["imported"] == 0
    assert db.session.query(Transaction).count() == 5


def test_wechat_accounts_are_matched_by_payment_method(auth_client):
    post_statement(auth_client, wechat_bytes(), dry_run=False)

    wechat_account = db.session.query(Account).filter_by(type="wechat").one()
    bank_account = db.session.query(Account).filter_by(type="bank").one()

    zero_rows = (
        db.session.query(Transaction)
        .filter(Transaction.payee.in_(["星巴克咖啡", "盒马鲜生", "滴滴出行"]))
        .all()
    )
    assert {txn.account_id for txn in zero_rows} == {wechat_account.id}

    transfer = db.session.query(Transaction).filter_by(payee="老王").one()
    assert transfer.account_id == bank_account.id


def test_alipay_categories_are_mapped(auth_client):
    raw = alipay_text().encode("utf-8")
    preview = post_statement(auth_client, raw).get_json()
    assert preview["source"] == "alipay"
    assert preview["ready"] == 5

    post_statement(auth_client, raw, dry_run=False)

    def category_name(payee: str) -> str:
        txn = db.session.query(Transaction).filter_by(payee=payee).one()
        return db.session.get(type(txn.category), txn.category_id).name  # type: ignore[arg-type]

    assert category_name("肯德基") == "餐饮"
    assert category_name("上海地铁") == "交通"
    assert category_name("淘宝") == "购物"
    assert category_name("小李") == "人情"
    assert category_name("余额宝") == "理财"  # 投资理财 -> 理财 via keyword/substring match


def test_gbk_encoded_statement_is_decoded(auth_client):
    raw = alipay_text().encode("gb18030")
    payload = post_statement(auth_client, raw).get_json()
    assert payload["encoding"] == "gb18030"
    assert payload["ready"] == 5


def test_utf8_bom_is_stripped(auth_client):
    raw = b"\xef\xbb\xbf" + wechat_bytes()
    payload = post_statement(auth_client, raw).get_json()
    assert payload["encoding"] == "utf-8-sig"
    assert payload["ready"] == 5


def test_default_category_and_account_are_used(auth_client, expense_category, account):
    payload = post_statement(
        auth_client,
        wechat_bytes(),
        dry_run=False,
        default_category_id=expense_category.id,
        default_account_id=account.id,
    ).get_json()
    assert payload["imported"] == 5

    # Rows whose payment method matches nothing fall back to the chosen account.
    transfer = db.session.query(Transaction).filter_by(payee="老王").one()
    assert transfer.account_id is not None


def test_same_statement_can_be_imported_by_two_users(auth_client, client, other_user):
    post_statement(auth_client, wechat_bytes(), dry_run=False)

    client.post("/api/auth/login", json={"email": other_user.email, "password": "s3cret-pass"})
    payload = post_statement(client, wechat_bytes(), dry_run=False).get_json()
    assert payload["imported"] == 5
    assert db.session.query(Transaction).count() == 10


def test_duplicate_rows_inside_one_file_are_collapsed(client, auth_client):
    rows = wechat_bytes().decode("utf-8").splitlines()
    header_index = next(i for i, line in enumerate(rows) if line.startswith("交易时间"))
    duplicate = rows[header_index + 1]
    # Two identical lines with no transaction id -> same synthetic external_id.
    forged = "\n".join(rows[: header_index + 1] + [duplicate.replace(",T2001,", ",,"), duplicate.replace(",T2001,", ",,")])
    payload = post_statement(auth_client, forged.encode("utf-8")).get_json()
    assert payload["duplicates"] == 1


def test_unrecognised_file_is_rejected(auth_client):
    response = post_statement(auth_client, b"a,b,c\n1,2,3\n")
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "unrecognised_statement"


def test_empty_and_missing_files_are_rejected(auth_client):
    empty = post_statement(auth_client, b"")
    assert empty.status_code == 400
    assert empty.get_json()["error"]["code"] == "empty_file"

    missing = auth_client.post(
        "/api/imports/csv", data={"dry_run": "true"}, content_type="multipart/form-data"
    )
    assert missing.status_code == 400
    assert missing.get_json()["error"]["code"] == "missing_file"


def test_import_requires_login(client):
    response = post_statement(client, wechat_bytes())
    assert response.status_code == 401


@pytest.mark.parametrize("field", ["default_category_id", "default_account_id"])
def test_bad_option_values_are_validated(auth_client, field):
    response = post_statement(auth_client, wechat_bytes(), **{field: "abc"})
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "validation_error"


def test_synthetic_external_ids_fit_the_column(auth_client):
    rows = wechat_bytes().decode("utf-8").splitlines()
    header_index = next(i for i, line in enumerate(rows) if line.startswith("交易时间"))
    stripped = [line.replace(",T2001,", ",,") for line in rows[header_index + 1 :]]
    forged = "\n".join(rows[: header_index + 1] + stripped)
    post_statement(auth_client, forged.encode("utf-8"), dry_run=False)

    for external_id in db.session.scalars(db.select(Transaction.external_id)).all():
        assert external_id is not None
        assert len(external_id) <= 128
