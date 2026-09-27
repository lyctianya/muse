"""财务三表 / 财务指标 / 主营业务构成。"""
from fastapi import APIRouter, Query

from ..deps import _conn

router = APIRouter()


@router.get("/api/financials")
def get_financials(
    market: str = Query(default="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
    type: str = Query(description="income|balance|cashflow|indicator",
                      pattern="^(income|balance|cashflow|indicator)$"),
):
    """财务三表 / 财务指标：按报告期倒序返回（含提取列 + 原始 data JSON）。"""
    tables = {
        "income": ("fin_income", ["revenue", "net_profit"]),
        "balance": ("fin_balance", ["total_assets", "total_liab"]),
        "cashflow": ("fin_cashflow", []),
        "indicator": ("fin_indicator", ["roe", "gross_margin", "net_margin"]),
    }
    table, extra_cols = tables[type]
    select_extra = ", " + ", ".join(extra_cols) if extra_cols else ""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT report_date{select_extra}, data FROM {table}"
                " WHERE market = %s AND symbol = %s ORDER BY report_date DESC",
                (market, symbol),
            )
            rows = cur.fetchall()
    out = []
    for r in rows:
        item = {"report_date": r[0].isoformat(), "data": r[-1]}
        for i, c in enumerate(extra_cols):
            v = r[1 + i]
            item[c] = float(v) if v is not None else None
        out.append(item)
    return out


@router.get("/api/business")
def get_business(
    market: str = Query(default="cn"),
    symbol: str = Query(description="股票代码，如 600519"),
):
    """主营业务构成：按报告期倒序。"""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT report_date, category, item, revenue, revenue_ratio,"
                " profit, profit_ratio FROM main_business"
                " WHERE market = %s AND symbol = %s"
                " ORDER BY report_date DESC, category, revenue DESC NULLS LAST",
                (market, symbol),
            )
            rows = cur.fetchall()
    return [
        {
            "report_date": r[0].isoformat(), "category": r[1], "item": r[2],
            "revenue": r[3], "revenue_ratio": r[4],
            "profit": r[5], "profit_ratio": r[6],
        }
        for r in rows
    ]
