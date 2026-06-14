"""Walk-Forward Analysis.

전체 기간 in-sample 최적화는 미래 성과를 보장하지 못한다. 워크포워드는 과거 구간(IS)에서
최적화한 파라미터를 "보지 않은" 다음 구간(OOS)에 적용해, OOS 성과의 일관성으로 robustness를
정직하게 평가한다.

핵심 처리:
- 워밍업: OOS 신호를 만들 때 앞쪽 IS 데이터를 워밍업으로 포함해 MA의 NaN 구간을 없앤다.
  성과 측정은 OOS 구간만. (IS 길이 >> slow이므로 워밍업은 항상 확보됨)
- 스티칭: 폴드별 OOS 일수익률을 이어붙여 연속 OOS 수익곡선을 만든다(폴드 간 비중복).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd

from . import engine, optimize
from .strategies import ma_cross_signals


@dataclass
class Fold:
    """폴드의 위치 인덱스(반열림 구간 [start, end))."""
    is_start: int
    is_end: int      # == oos_start
    oos_end: int


def make_folds(
    n: int,
    is_len: int,
    oos_len: int,
    anchored: bool = False,
) -> list[Fold]:
    """길이 n인 시계열을 IS/OOS 폴드로 분할.

    rolling(기본): 고정 길이 IS가 oos_len씩 슬라이딩.
    anchored: IS 시작은 0으로 고정되고 끝이 확장.
    OOS는 항상 비중복으로 연속된다.
    """
    folds: list[Fold] = []
    is_end = is_len
    while is_end + oos_len <= n:
        is_start = 0 if anchored else is_end - is_len
        folds.append(Fold(is_start=is_start, is_end=is_end, oos_end=is_end + oos_len))
        is_end += oos_len
    return folds


def walk_forward(
    close: pd.Series,
    fasts: Sequence[int],
    slows: Sequence[int],
    is_len: int = 756,
    oos_len: int = 252,
    fees: float = 0.00015,
    slippage: float = 0.001,
    anchored: bool = False,
) -> tuple[pd.DataFrame, pd.Series]:
    """워크포워드 실행.

    Returns:
        (folds_df, oos_returns)
        - folds_df: 폴드별 [fast, slow, is_sharpe, oos_sharpe, oos_return, 기간].
        - oos_returns: 폴드별 OOS 일수익률을 이어붙인 연속 시리즈(스티칭 결과).
    """
    warmup = max(slows)  # OOS 신호 워밍업에 필요한 최대 lookback
    folds = make_folds(len(close), is_len, oos_len, anchored)
    if not folds:
        raise ValueError(
            f"데이터({len(close)}일)가 is_len+oos_len({is_len}+{oos_len})보다 짧습니다."
        )

    rows = []
    oos_chunks: list[pd.Series] = []

    for i, fold in enumerate(folds, 1):
        # 1) IS 구간에서 최적 파라미터 선정
        is_close = close.iloc[fold.is_start:fold.is_end]
        is_res = optimize.grid_search(is_close, fasts, slows, fees=fees, slippage=slippage)
        (best_fast, best_slow) = is_res.index[0]
        is_sharpe = float(is_res.iloc[0]["sharpe"])

        # 2) OOS: 워밍업 포함 슬라이스로 신호 생성 → OOS 구간 수익률만 수집
        sig_start = fold.is_end - warmup  # IS 길이 >> warmup 이므로 항상 >= 0
        sig_close = close.iloc[sig_start:fold.oos_end]
        entries, exits = ma_cross_signals(sig_close, int(best_fast), int(best_slow))
        pf = engine.run(sig_close, entries, exits, fees=fees, slippage=slippage)

        oos_ret = pf.returns().iloc[warmup:]  # 워밍업 구간 제외 = OOS만
        oos_chunks.append(oos_ret)

        # OOS 샤프(연율화)는 이 수익률 조각에서 직접 계산
        std = oos_ret.std()
        oos_sharpe = float(oos_ret.mean() / std * np.sqrt(252)) if std > 0 else float("nan")
        oos_total = float((1.0 + oos_ret).prod() - 1.0)

        rows.append({
            "fold": i,
            "oos_start": oos_ret.index[0].date(),
            "oos_end": oos_ret.index[-1].date(),
            "fast": int(best_fast),
            "slow": int(best_slow),
            "is_sharpe": is_sharpe,
            "oos_sharpe": oos_sharpe,
            "oos_return": oos_total,
        })

    folds_df = pd.DataFrame(rows).set_index("fold")
    oos_returns = pd.concat(oos_chunks)
    return folds_df, oos_returns
