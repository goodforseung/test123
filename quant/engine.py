"""백테스트 실행 엔진 (vectorbt 래퍼).

핵심 책임:
1. look-ahead bias 방지 — 신호는 종가(t)에 계산되지만 체결은 다음 봉(t+1)에서.
   vectorbt는 기본적으로 같은 봉에서 체결하므로, 신호를 1봉 밀어(shift) 강제한다.
2. 현실적 비용 — 수수료/슬리피지를 broker에 반영(한국·미국 차이는 파라미터로 주입).
"""
from __future__ import annotations

import pandas as pd
import vectorbt as vbt


def run(
    close: pd.Series,
    entries: pd.Series,
    exits: pd.Series,
    init_cash: float = 1e7,
    fees: float = 0.00015,
    slippage: float = 0.001,
    freq: str = "1D",
    shift: bool = True,
) -> vbt.Portfolio:
    """시그널을 받아 백테스트를 실행하고 Portfolio를 반환한다.

    Args:
        close: 종가 시계열.
        entries, exits: ma_cross_signals 등이 만든 불리언 시그널.
        init_cash: 초기 자본.
        fees: 거래당 수수료율(편도). 한국 위탁수수료≈0.015%, 미국≈0. 매도세는 별도.
        slippage: 체결 슬리피지율.
        freq: 수익률 연율화용 빈도("1D"=일봉).
        shift: True면 신호를 1봉 미뤄 다음 봉에서 체결(look-ahead 방지). 기본 True.

    Returns:
        vectorbt Portfolio 객체.
    """
    if shift:
        # 종가(t)에서 난 신호를 t+1에 실행. fillna(False)로 첫 봉 NaN 정리.
        entries = entries.shift(1).fillna(False).astype(bool)
        exits = exits.shift(1).fillna(False).astype(bool)

    return vbt.Portfolio.from_signals(
        close,
        entries,
        exits,
        init_cash=init_cash,
        fees=fees,
        slippage=slippage,
        freq=freq,
    )
