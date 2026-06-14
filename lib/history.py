"""백테스트 기록 영속화 — Supabase(외부 Postgres) 연동.

Streamlit Community Cloud는 파일시스템이 휘발성이라 로컬 파일로는 재배포 시 기록이 사라진다.
외부 DB(Supabase)에 적립해 배포 환경에서도 영구 보존한다.

연결은 공식 권장 방식인 st.connection + st_supabase_connection 커넥터를 쓰며,
자격증명은 .streamlit/secrets.toml 의 [connections.supabase] 에서 자동 로드된다.

시크릿이 없거나 연결 실패해도 앱이 죽지 않도록 모든 함수는 예외를 잡아 안내한다.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from st_supabase_connection import SupabaseConnection

TABLE = "backtests"

# DB에 적재하는 컬럼(테이블 스키마와 일치)
COLUMNS = [
    "symbol", "start_date", "end_date", "fast", "slow", "fees", "slippage",
    "total_return", "cagr", "max_drawdown", "sharpe", "win_rate", "num_trades",
]


def _conn() -> SupabaseConnection:
    """Supabase 연결. [connections.supabase]의 url/key를 명시적으로 전달.

    (st.connection의 섹션→kwarg 자동전달은 환경에 따라 불안정해서, 시크릿을 직접 읽어
    url/key kwarg로 넘긴다 — 커넥터가 가장 우선시하는 경로.)
    """
    sec = st.secrets["connections"]["supabase"]
    return st.connection("supabase", type=SupabaseConnection,
                         url=sec["url"], key=sec["key"])


def is_configured() -> bool:
    """시크릿에 supabase 연결 정보가 있는지 확인."""
    try:
        return "supabase" in st.secrets.get("connections", {})
    except Exception:
        return False


def save_backtest(record: dict) -> tuple[bool, str]:
    """백테스트 1건을 기록. (성공여부, 메시지) 반환."""
    if not is_configured():
        return False, "Supabase 시크릿이 설정되지 않았습니다. (.streamlit/secrets.toml)"
    try:
        row = {k: record.get(k) for k in COLUMNS}
        _conn().table(TABLE).insert(row).execute()
        return True, "기록을 저장했습니다."
    except Exception as e:
        return False, f"저장 실패: {e}"


def load_history(limit: int = 200) -> pd.DataFrame:
    """최근 기록을 created_at 내림차순으로 조회. 실패 시 빈 DataFrame."""
    if not is_configured():
        return pd.DataFrame()
    try:
        res = (
            _conn()
            .table(TABLE)
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return pd.DataFrame(res.data)
    except Exception:
        return pd.DataFrame()


def clear_history() -> tuple[bool, str]:
    """전체 기록 삭제."""
    if not is_configured():
        return False, "Supabase 시크릿이 설정되지 않았습니다."
    try:
        # id >= 0 조건으로 전체 행 삭제
        _conn().table(TABLE).delete().gte("id", 0).execute()
        return True, "모든 기록을 삭제했습니다."
    except Exception as e:
        return False, f"삭제 실패: {e}"
