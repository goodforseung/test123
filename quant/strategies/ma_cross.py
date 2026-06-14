"""이동평균 교차 전략 (예제).

전략 = "가격 시계열을 받아 진입/청산 불리언 시그널을 만드는 함수"로 정의한다.
실제 체결 타이밍(다음 봉 실행으로 look-ahead 방지)과 비용은 engine.run에서 처리하므로,
여기서는 순수하게 신호 로직만 담당한다.
"""
from __future__ import annotations

from typing import Sequence

import pandas as pd
import vectorbt as vbt

# fast/slow가 스칼라(단일 전략) 또는 시퀀스(그리드서치)로 모두 들어올 수 있다.
IntOrSeq = int | Sequence[int]


def ma_cross_signals(
    close: pd.Series,
    fast: IntOrSeq = 20,
    slow: IntOrSeq = 60,
):
    """단기/장기 이동평균 골든·데드크로스 시그널.

    Args:
        close: 종가 시계열 (DatetimeIndex).
        fast: 단기 이동평균 기간. 스칼라 또는 정수 리스트.
        slow: 장기 이동평균 기간. 스칼라 또는 정수 리스트.

    Returns:
        (entries, exits):
            - fast/slow 모두 스칼라면 불리언 Series.
            - 하나라도 리스트면 fast×slow 곱집합을 컬럼으로 갖는 멀티파라미터 불리언 DataFrame.
              컬럼은 MultiIndex(fast_window, slow_window, ...) 형태(vectorbt 규칙).
        entries = 단기선이 장기선을 상향 돌파(골든크로스)
        exits   = 단기선이 장기선을 하향 돌파(데드크로스)

    주의: 모든 이동평균은 close[t]까지만 사용하므로 이 신호 자체에는 look-ahead가 없다.
    체결 시점 분리는 engine.run(shift=True)이 담당한다.
    vbt.MA.run은 리스트를 그대로 받아 멀티파라미터 인디케이터를 만들고,
    ma_crossed_above/below가 fast×slow 곱집합 컬럼을 자동 생성한다.
    """
    fast_ma = vbt.MA.run(close, fast, short_name="fast")
    slow_ma = vbt.MA.run(close, slow, short_name="slow")
    entries = fast_ma.ma_crossed_above(slow_ma)
    exits = fast_ma.ma_crossed_below(slow_ma)
    return entries, exits
