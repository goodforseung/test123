"""파라미터 그리드서치 + 히트맵.

조사 결과 파라미터 튜닝은 overfitting에 가장 취약한 단계다. 그래서 단일 "최고 샤프"를
좇기보다 파라미터 표면을 히트맵으로 보고 안정적인 고원(plateau)을 고르는 걸 목표로 한다.
멀티테스팅(selection bias) 환기를 위해 테스트한 조합 수도 함께 보고한다.
정식 Deflated Sharpe Ratio는 다음 단계(워크포워드)에서.
"""
from __future__ import annotations

import os
from typing import Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# 선정 시 퇴화 조합(거래 거의 없음→샤프 발산)을 거르는 최소 거래 수 기본값
MIN_TRADES = 3

from . import engine
from .strategies import ma_cross_signals


def grid_search(
    close: pd.Series,
    fasts: Sequence[int],
    slows: Sequence[int],
    fees: float = 0.00015,
    slippage: float = 0.001,
    min_trades: int = MIN_TRADES,
) -> pd.DataFrame:
    """fast×slow 조합(단, fast<slow)을 한 번에 백테스트해 지표 표를 반환.

    유효 조합만 두 동일길이 리스트로 만들어 넘기면 vectorbt가 element-wise로
    페어링하므로, 무효 조합(fast>=slow)은 애초에 생성되지 않는다.

    퇴화 조합(거래 < min_trades 또는 샤프가 비유한)은 sharpe를 NaN으로 만들어
    정렬 시 맨 아래로 보낸다. 표/히트맵에는 남기되 "최고"로는 선정되지 않게 한다.

    Returns:
        index=(fast, slow) MultiIndex, columns=[sharpe, total_return, max_drawdown,
        num_trades]를 sharpe 내림차순 정렬한 DataFrame.
    """
    combos = [(f, s) for f in fasts for s in slows if f < s]
    if not combos:
        raise ValueError("유효한 (fast<slow) 조합이 없습니다.")
    fast_list = [c[0] for c in combos]
    slow_list = [c[1] for c in combos]

    entries, exits = ma_cross_signals(close, fast_list, slow_list)
    pf = engine.run(close, entries, exits, fees=fees, slippage=slippage)

    # 각 지표는 컬럼 MultiIndex(fast_window, slow_window)로 인덱싱된 Series로 나온다.
    res = pd.DataFrame(
        {
            "sharpe": pf.sharpe_ratio().values,
            "total_return": pf.total_return().values,
            "max_drawdown": pf.max_drawdown().values,
            "num_trades": pf.trades.count().values,
        },
        index=pd.MultiIndex.from_tuples(combos, names=["fast", "slow"]),
    )
    # 거래 부족·비유한 샤프(변동성≈0으로 발산) 조합은 선정 대상에서 제외
    degenerate = (res["num_trades"] < min_trades) | ~np.isfinite(res["sharpe"])
    res.loc[degenerate, "sharpe"] = np.nan
    return res.sort_values("sharpe", ascending=False)  # NaN은 기본적으로 맨 아래


def print_top(results: pd.DataFrame, n: int = 5, title: str = "") -> None:
    """상위 n개 + 테스트한 총 조합 수(멀티테스팅 환기)를 출력."""
    head = f" {title} " if title else " "
    print(f"\n{'='*52}\n{head.center(52, '=')}\n{'='*52}")
    print(f"테스트한 조합 수: {len(results)}개  (selection bias 주의)")
    top = results.head(n)
    print(f"\n[상위 {n}개 — sharpe 기준]")
    for (fast, slow), row in top.iterrows():
        print(
            f"  fast={fast:>3} slow={slow:>3} | "
            f"sharpe {row['sharpe']:5.2f} | "
            f"수익 {row['total_return']:+7.1%} | "
            f"MDD {row['max_drawdown']:6.1%} | "
            f"거래 {int(row['num_trades']):>3}"
        )


def heatmap(
    results: pd.DataFrame,
    path: str,
    metric: str = "sharpe",
    title: str = "Parameter Surface",
) -> str:
    """(fast×slow) 파라미터 표면을 히트맵 PNG로 저장.

    spike(한 점만 높음=overfit 위험) 대 plateau(주변까지 고르게 높음=robust)를
    눈으로 구분하는 용도.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    grid = results[metric].unstack("slow")  # index=fast, columns=slow

    fig, ax = plt.subplots(figsize=(10, 6))
    mesh = ax.pcolormesh(
        grid.columns.astype(float),
        grid.index.astype(float),
        grid.values,
        cmap="viridis",
        shading="auto",
    )
    fig.colorbar(mesh, ax=ax, label=metric)
    ax.set_xlabel("slow window")
    ax.set_ylabel("fast window")
    ax.set_title(f"{title} ({metric})")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path
