"""CSV export, the manual backstop for the personal-data backup story."""

from __future__ import annotations

import csv
import io
from datetime import date

from flask import Blueprint, Response, request
from flask_login import login_required

from ..services import stats as stats_service
from ..utils.time import add_months, today_local
from .helpers import current_user_id

bp = Blueprint("exports", __name__, url_prefix="/exports")

CSV_HEADER = ["日期", "类型", "分类", "账户", "金额(元)", "商户", "备注"]


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


@bp.get("/transactions.csv")
@login_required
def export_transactions_csv():
    today = today_local()
    # Default to the last 12 months; ``date_from=1900-01-01`` exports everything.
    default_from = add_months(today.replace(day=1), -11)
    date_from = _parse_date(request.args.get("date_from")) or default_from
    date_to = _parse_date(request.args.get("date_to")) or today

    header_line = io.StringIO()
    csv.writer(header_line).writerow(CSV_HEADER)

    # Materialise the rows while the request context (and DB session) is still
    # alive: the generator below runs after Flask tore that context down.
    rows = list(stats_service.iter_export_rows(current_user_id(), date_from, date_to))

    def generate():
        # UTF-8 BOM so Excel on Windows opens Chinese text correctly.
        yield "\ufeff" + header_line.getvalue()
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        for row in rows:
            writer.writerow(row)
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    filename = f"dailyspend-{date_from.isoformat()}_{date_to.isoformat()}.csv"
    return Response(
        generate(),
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
