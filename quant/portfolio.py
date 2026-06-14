"""멀티종목 포트폴리오 — 동일비중 vs 역변동성(volatility parity).

단일종목 추세추종은 시장 전환에 취약하다(단계 2-B에서 확인). 다수 종목에 분산하면
일부 종목의 추세가 끊겨도 다른 종목이 받쳐줘 곡선이 안정된다. 핵심은 포지션 사이징:
- 동일비중: 보유 중 종목에 1/N
- 역변동성: 변동성 큰 종목엔 적게, 작은 종목엔 많이 → 각 종목이 리스크를 동등 기여

현금 공유 단일 포트폴리오(실제 한 계좌)로 vectorbt from_orders(TargetPercent)를 쓴다.
리밸런싱 날짜에만 목표비중을 갱신하고, 비중은 1봉 shift해 look-ahead를 방지한다.
"""
from __future__ import annotations

import pandas as pd
import vectorbt as vbt

from .strategies import ma_cross_signals


def holding_state(close_df: pd.DataFrame, fast: int = 20, slow: int = 60) -> pd.DataFrame:
    """종목별 보유상태(0/1) 행렬.

    골든크로스 시 1, 데드크로스 시 0, 그 사이는 직전 상태 유지(ffill).
    ma_cross_signals는 DataFrame 입력 시 컬럼(종목)별 신호를 자동 생성한다.
    """
    entries, exits = ma_cross_signals(close_df, fast, slow)
    # 진입=1, 청산=0 마킹 후 ffill로 보유 구간을 채운다.
    state = pd.DataFrame(index=close_df.index, columns=close_df.columns, dtype="float64")
    state[entries.values] = 1.0
    state[exits.values] = 0.0
    return state.ffill().fillna(0.0)


def target_weights(
    holding: pd.DataFrame,
    returns: pd.DataFrame,
    scheme: str = "equal",
    vol_window: int = 20,
) -> pd.DataFrame:
    """보유상태 → 목표비중 행렬(행합 ≤ 1; 보유 0이면 전부 현금).

    scheme:
        "equal"       — 보유 중 종목에 1/N.
        "inverse_vol" — w_i ∝ 보유_i / 변동성_i, 행 단위 정규화.
    """
    if scheme == "equal":
        raw = holding.copy()
    elif scheme == "inverse_vol":
        vol = returns.rolling(vol_window).std()
        # 변동성이 NaN/0인 초기 구간은 비중 0이 되도록 처리
        inv_vol = (1.0 / vol).replace([float("inf"), -float("inf")], 0.0).fillna(0.0)
        raw = holding * inv_vol
    else:
        raise ValueError(f"알 수 없는 scheme: {scheme}")

    row_sum = raw.sum(axis=1)
    # 보유 종목이 하나도 없는 날은 0으로 나누지 않도록 가드
    weights = raw.div(row_sum.where(row_sum > 0), axis=0).fillna(0.0)
    return weights


def apply_rebalance(weights: pd.DataFrame, freq: str = "M") -> pd.DataFrame:
    """리밸런싱 날짜에만 목표비중을 갱신하고 사이 구간은 ffill.

    freq: pandas period alias("M"=월간, "W"=주간 등). 너무 잦으면 비용↑.
    각 주기의 마지막 거래일을 리밸런싱 날짜로 잡는다(존재하는 거래일만 사용).
    """
    # 각 period의 마지막 실제 거래일 = 리밸런싱 날짜
    day = pd.Series(weights.index, index=weights.index)
    rebal_days = pd.DatetimeIndex(day.groupby(weights.index.to_period(freq)).last().values)

    # 행 단위 마스크(Series)를 axis=0으로 브로드캐스트 → 리밸런싱 날만 값 유지, 나머지 NaN
    mask = pd.Series(weights.index.isin(rebal_days), index=weights.index)
    held = weights.where(mask, axis=0)
    held.iloc[0] = weights.iloc[0]  # 첫날은 항상 초기 비중 설정
    return held.ffill().fillna(0.0)


def run_portfolio(
    close_df: pd.DataFrame,
    fast: int = 20,
    slow: int = 60,
    scheme: str = "equal",
    rebalance: str = "M",
    fees: float = 0.00015,
    slippage: float = 0.001,
    init_cash: float = 1e7,
    vol_window: int = 20,
) -> vbt.Portfolio:
    """멀티종목 현금공유 포트폴리오를 목표비중 리밸런싱으로 실행."""
    returns = close_df.pct_change()
    holding = holding_state(close_df, fast, slow)
    weights = target_weights(holding, returns, scheme=scheme, vol_window=vol_window)
    weights = apply_rebalance(weights, freq=rebalance)
    return execute_weights(close_df, weights, fees=fees, slippage=slippage, init_cash=init_cash)


def execute_weights(
    close_df: pd.DataFrame,
    weights: pd.DataFrame,
    fees: float = 0.00015,
    slippage: float = 0.001,
    init_cash: float = 1e7,
    shift: bool = True,
) -> vbt.Portfolio:
    """목표비중 행렬을 현금공유 단일 포트폴리오로 체결.

    MA 포트폴리오·팩터 포트폴리오가 공유하는 실행부.
    shift=True면 비중을 1봉 미뤄 체결(look-ahead 방지).
    """
    if shift:
        # look-ahead 방지: t 정보로 만든 목표비중을 t+1에 체결
        weights = weights.shift(1).fillna(0.0)

    return vbt.Portfolio.from_orders(
        close=close_df,
        size=weights,
        size_type="targetpercent",
        group_by=True,          # 전 종목을 하나의 포트폴리오로 묶음
        cash_sharing=True,      # 종목 간 현금 공유(단일 계좌)
        call_seq="auto",        # 매도 먼저 체결 → 현금 확보 후 매수
        fees=fees,
        slippage=slippage,
        init_cash=init_cash,
        freq="1D",
    )
