"""RSI 평균회귀 전략.

RSI가 과매도(기본 30) 아래로 떨어지면 매수, 과매수(기본 70) 위로 올라가면 매도.
추세추종(MA 교차)과 반대로, 과도하게 빠진 걸 사고 과열되면 파는 평균회귀 접근.
"""
from __future__ import annotations

import pandas as pd
import vectorbt as vbt


def rsi_signals(close: pd.Series, period: int = 14, lower: float = 30, upper: float = 70):
    """RSI 과매도/과매수 교차 시그널.

    Returns:
        (entries, exits) 불리언 Series.
        entries = RSI가 lower를 하향 돌파(과매도 진입)
        exits   = RSI가 upper를 상향 돌파(과매수)
    """
    rsi = vbt.RSI.run(close, window=period)
    entries = rsi.rsi_crossed_below(lower)
    exits = rsi.rsi_crossed_above(upper)
    return entries, exits
