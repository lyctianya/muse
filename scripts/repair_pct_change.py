"""修复 daily_bars.pct_change 数据质量问题（一次性）。

修复两类问题：
1. pct_change 为 NULL 的行：用前一交易日收盘价补算
   （首日数据无前收，属正常，会保留 NULL）
2. pct_change 与 (close - 前收) / 前收 严重不符（>1个百分点）的行：
   重算为与收盘价自洽的值

用法：
    python scripts/repair_pct_change.py
    python scripts/repair_pct_change.py --db postgresql://... --market hk

幂等：重跑安全，只改确实有问题的行。
"""
import argparse
import logging
import os
import sys
from pathlib import Path

import psycopg

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]


def load_database_url(cli_db: str) -> str:
    if cli_db:
        return cli_db
    env_url = os.environ.get("DATABASE_URL", "")
    if env_url:
        return env_url
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("Pass --db, or set DATABASE_URL / project .env")


FILL_NULL_SQL = """
WITH ranked AS (
  SELECT symbol, trade_date, close,
         LAG(close) OVER (PARTITION BY symbol ORDER BY trade_date) AS prev_close
  FROM daily_bars WHERE market = %s
)
UPDATE daily_bars b
SET pct_change = ROUND(((r.close - r.prev_close) / r.prev_close * 100)::numeric, 4)
FROM ranked r
WHERE b.market = %s AND b.symbol = r.symbol AND b.trade_date = r.trade_date
  AND b.pct_change IS NULL
  AND r.prev_close IS NOT NULL AND r.prev_close <> 0
"""

FIX_WRONG_SQL = """
WITH t AS (
  SELECT symbol, trade_date, close, pct_change,
         LAG(close) OVER (PARTITION BY symbol ORDER BY trade_date) AS prev_c
  FROM daily_bars WHERE market = %s
)
UPDATE daily_bars b
SET pct_change = ROUND(((t.close - t.prev_c) / t.prev_c * 100)::numeric, 4)
FROM t
WHERE b.market = %s AND b.symbol = t.symbol AND b.trade_date = t.trade_date
  AND b.pct_change IS NOT NULL
  AND t.prev_c IS NOT NULL AND t.prev_c <> 0
  AND ABS(b.pct_change - (t.close - t.prev_c) / t.prev_c * 100) > 1.0
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="修复 pct_change 数据")
    ap.add_argument("--db", default="", help="DB 连接串")
    ap.add_argument("--market", default="", help="只修某市场（cn/hk/us），缺省全部")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s: %(message)s")
    conn = psycopg.connect(load_database_url(args.db))
    conn.autocommit = True
    try:
        markets = [args.market] if args.market else ["cn", "hk", "us"]
        for m in markets:
            with conn.cursor() as cur:
                cur.execute(FILL_NULL_SQL, (m, m))
                n1 = cur.rowcount
                cur.execute(FIX_WRONG_SQL, (m, m))
                n2 = cur.rowcount
                cur.execute(
                    "SELECT COUNT(*) FROM daily_bars "
                    "WHERE market = %s AND pct_change IS NULL", (m,))
                still_null = cur.fetchone()[0]
            log.info("[%s] 补算空值 %d 行，修正错误值 %d 行，剩余空值 %d（首日正常）",
                     m, n1, n2, still_null)
    finally:
        conn.close()
    log.info("ALL DONE")


if __name__ == "__main__":
    main()
