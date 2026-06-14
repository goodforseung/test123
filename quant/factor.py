"""가격 기반 크로스섹셔널 팩터 — 모멘텀 · 저변동성.

MA(시계열 추세추종)와 달리, 팩터는 "종목 간 상대 랭킹"이다. 매 리밸런싱일에 점수로 정렬해
상위 분위(예: 20%)를 동일비중 매수한다. 점수는 "높을수록 매수 선호"로 통일한다.

- 모멘텀(Jegadeesh-Titman 12-1): 과거 12개월 누적수익률, 최근 1개월(skip)은 제외(단기반전 회피).
- 저변동성: 트레일링 변동성이 낮을수록 우수 → 점수를 −변동성으로 둔다.

실행은 portfolio.execute_weights를 재사용(현금공유 단일 포트폴리오 + look-ahead shift).
"""
from __future__ import annotations

import pandas as pd
import vectorbt as vbt

from . import portfolio


def momentum_score(close_df: pd.DataFrame, lookback: int = 252, skip: int = 21) -> pd.DataFrame:
    """12-1 모멘텀 점수 = close[t-skip] / close[t-lookback] − 1 (높을수록 우수)."""
    return close_df.shift(skip) / close_df.shift(lookback) - 1.0


def vol_score(close_df: pd.DataFrame, window: int = 252) -> pd.DataFrame:
    """저변동성 점수 = −(트레일링 변동성). 변동성이 낮을수록 점수가 높다."""
    returns = close_df.pct_change()
    return -returns.rolling(window).std()


def quantile_weights(score: pd.DataFrame, q: float = 0.2, rebalance: str = "M") -> pd.DataFrame:
    """점수 상위 q 분위를 동일비중으로 담는 목표비중 행렬.

    q=1.0이면 전 종목 동일비중(벤치마크). 행합 ≤ 1, 음수 없음.
    리밸런싱일에만 갱신(portfolio.apply_rebalance 재사용).
    """
    # 행별 랭크: 1 = 점수 최고. 점수 NaN(데이터 부족 구간)은 선택 제외.
    ranks = score.rank(axis=1, ascending=False)
    n_valid = score.notna().sum(axis=1)
    n_select = (n_valid * q).round().clip(lower=1)        # 분위당 선택 종목 수(최소 1)

    selected = ranks.le(n_select, axis=0) & score.notna()  # 상위 분위 불리언
    counts = selected.sum(axis=1)
    weights = selected.div(counts.where(counts > 0), axis=0).fillna(0.0)
    return portfolio.apply_rebalance(weights, freq=rebalance)


def run_factor(
    close_df: pd.DataFrame,
    kind: str = "momentum",
    q: float = 0.2,
    rebalance: str = "M",
    fees: float = 0.00015,
    slippage: float = 0.001,
    init_cash: float = 1e7,
) -> vbt.Portfolio:
    """팩터 포트폴리오 실행. kind: 'momentum' | 'low_vol' | 'equal'(벤치마크)."""
    if kind == "momentum":
        score = momentum_score(close_df)
    elif kind == "low_vol":
        score = vol_score(close_df)
    elif kind == "equal":
        # 상수 점수 + q=1.0 → 전 종목 동일비중 벤치마크
        score = pd.DataFrame(1.0, index=close_df.index, columns=close_df.columns)
        q = 1.0
    else:
        raise ValueError(f"알 수 없는 kind: {kind}")

    weights = quantile_weights(score, q=q, rebalance=rebalance)
    return portfolio.execute_weights(close_df, weights, fees=fees, slippage=slippage,
                                     init_cash=init_cash)
