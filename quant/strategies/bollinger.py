"""볼린저밴드 평균회귀 전략.

가격이 하단 밴드를 하향 이탈하면 매수(과도한 하락), 상단 밴드를 상향 돌파하면 매도.
밴드는 이동평균 ± n_std·표준편차. 횡보장에서 잘 통하고 강한 추세장에선 약하다.
"""
from __future__ import annotations

import pandas as pd
import vectorbt as vbt


def bollinger_signals(close: pd.Series, window: int = 20, n_std: float = 2.0):
    """볼린저밴드 하단 이탈 매수 / 상단 돌파 매도 시그널.

    Returns:
        (entries, exits) 불리언 Series.
        entries = 종가가 하단 밴드를 하향 돌파
        exits   = 종가가 상단 밴드를 상향 돌파
    """
    bb = vbt.BBANDS.run(close, window=window, alpha=n_std)
    entries = close.vbt.crossed_below(bb.lower)
    exits = close.vbt.crossed_above(bb.upper)
    return entries, exits
