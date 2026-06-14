"""성과 분석 — Portfolio에서 핵심 지표를 뽑고 수익곡선을 그린다."""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")  # 헤드리스 환경에서 파일 저장용
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import vectorbt as vbt

# 연율화 상수: 일봉 기준 1년 거래일 수
_TRADING_DAYS = 252


def summary(pf: vbt.Portfolio) -> dict:
    """핵심 성과 지표를 dict로 반환.

    누적수익률 / CAGR / MDD / 샤프 / 승률 / 거래횟수.
    값이 없는 경우(거래 0건 등)는 0 또는 NaN을 그대로 둔다.
    """
    trades = pf.trades
    return {
        "total_return": float(pf.total_return()),          # 누적 수익률
        "cagr": float(pf.annualized_return()),             # 연복리 수익률
        "max_drawdown": float(pf.max_drawdown()),          # 최대 낙폭(MDD)
        "sharpe": float(pf.sharpe_ratio()),                # 샤프 지수
        "win_rate": float(trades.win_rate()) if trades.count() > 0 else 0.0,
        "num_trades": int(trades.count()),
    }


def print_summary(pf: vbt.Portfolio, title: str = "") -> dict:
    """summary를 보기 좋게 출력하고 dict도 반환."""
    s = summary(pf)
    head = f" {title} " if title else " "
    print(f"\n{'='*40}\n{head.center(40, '=')}\n{'='*40}")
    print(f"누적수익률   : {s['total_return']:+.2%}")
    print(f"CAGR        : {s['cagr']:+.2%}")
    print(f"MDD         : {s['max_drawdown']:.2%}")
    print(f"샤프지수     : {s['sharpe']:.2f}")
    print(f"승률        : {s['win_rate']:.2%}")
    print(f"거래횟수     : {s['num_trades']}")
    return s


def summary_from_returns(returns: pd.Series, trading_days: int = _TRADING_DAYS) -> dict:
    """일수익률 Series에서 핵심 지표를 직접 계산.

    워크포워드처럼 폴드별 OOS 수익률을 이어붙인 시리즈를 평가할 때 사용한다
    (Portfolio 객체가 아니라 순수 수익률 시계열이 입력).

    Returns:
        total_return / cagr / max_drawdown / sharpe / num_days.
    """
    r = returns.dropna()
    if len(r) == 0:
        return {"total_return": 0.0, "cagr": 0.0, "max_drawdown": 0.0,
                "sharpe": float("nan"), "num_days": 0}

    equity = (1.0 + r).cumprod()
    total_return = float(equity.iloc[-1] - 1.0)
    years = len(r) / trading_days
    cagr = float(equity.iloc[-1] ** (1.0 / years) - 1.0) if years > 0 else 0.0
    drawdown = equity / equity.cummax() - 1.0
    max_dd = float(drawdown.min())
    std = r.std()
    sharpe = float(r.mean() / std * np.sqrt(trading_days)) if std > 0 else float("nan")

    return {
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "num_days": int(len(r)),
    }


def plot_returns_equity(returns: pd.Series, path: str, title: str = "Equity Curve") -> str:
    """일수익률 → 누적곱 자산곡선 PNG 저장(초기자본 1로 정규화)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    equity = (1.0 + returns.dropna()).cumprod()

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(equity.index, equity.values, linewidth=1.2)
    ax.axhline(1.0, color="gray", linewidth=0.8, linestyle="--", alpha=0.6)
    ax.set_title(title)
    ax.set_ylabel("Growth of 1")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def plot_equity(pf: vbt.Portfolio, path: str, title: str = "Equity Curve") -> str:
    """포트폴리오 가치(자산 곡선)를 PNG로 저장하고 경로를 반환."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    value = pf.value()

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(value.index, value.values, linewidth=1.2)
    ax.set_title(title)
    ax.set_ylabel("Portfolio Value")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path
