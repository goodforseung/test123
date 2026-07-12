"""자동매매 저널 조회 — Supabase trade_journal (읽기 전용).

메인 Quant 프로젝트의 신호→주문 루프가 로컬 JSONL 저널을 Supabase로 미러하고,
이 모듈은 그 미러를 읽기만 한다(대시보드에서 매매 기록을 수정·삭제하지 않음 —
원본은 로컬 파일이라 여기서 지워도 다음 실행 때 되살아난다).
"""
from __future__ import annotations

import pandas as pd

from lib.history import _conn, is_configured

TABLE = "trade_journal"


def load_latest_report() -> dict | None:
    """가장 최근 daily_report 이벤트의 payload(리포트 전문)를 반환. 없으면 None."""
    if not is_configured():
        return None
    try:
        res = (
            _conn()
            .table(TABLE)
            .select("payload")
            .eq("event", "daily_report")
            .order("ts", desc=True)
            .limit(1)
            .execute()
        )
        return res.data[0]["payload"] if res.data else None
    except Exception:
        return None


def load_latest_virtual() -> dict | None:
    """가장 최근 virtual_state(가상 포트폴리오) payload를 반환. 없으면 None."""
    if not is_configured():
        return None
    try:
        res = (
            _conn()
            .table(TABLE)
            .select("payload")
            .eq("event", "virtual_state")
            .order("ts", desc=True)
            .limit(1)
            .execute()
        )
        return res.data[0]["payload"] if res.data else None
    except Exception:
        return None


def load_journal(limit: int = 500) -> pd.DataFrame:
    """최근 이벤트를 ts 내림차순으로 조회. 실패 시 빈 DataFrame."""
    if not is_configured():
        return pd.DataFrame()
    try:
        res = (
            _conn()
            .table(TABLE)
            .select("*")
            .order("ts", desc=True)
            .limit(limit)
            .execute()
        )
        return pd.DataFrame(res.data)
    except Exception:
        return pd.DataFrame()
