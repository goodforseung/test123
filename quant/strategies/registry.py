"""단일종목 전략 레지스트리 — UI가 데이터로 읽어 동적 렌더링.

각 전략: {fn, params:[{key,label,min,max,default,step?}]}.
새 전략을 추가하면 app.py 수정 없이 드롭다운·슬라이더가 자동 갱신된다.
모든 fn은 (close: Series, **params) -> (entries, exits) 시그니처를 따른다.
"""
from __future__ import annotations

from .ma_cross import ma_cross_signals
from .rsi import rsi_signals
from .bollinger import bollinger_signals

SINGLE_STRATEGIES = {
    "이동평균 교차": {
        "fn": ma_cross_signals,
        "params": [
            {"key": "fast", "label": "Fast MA", "min": 3, "max": 100, "default": 20},
            {"key": "slow", "label": "Slow MA", "min": 10, "max": 300, "default": 60},
        ],
    },
    "RSI": {
        "fn": rsi_signals,
        "params": [
            {"key": "period", "label": "RSI 기간", "min": 2, "max": 50, "default": 14},
            {"key": "lower", "label": "과매도(매수) 기준", "min": 5, "max": 45, "default": 30},
            {"key": "upper", "label": "과매수(매도) 기준", "min": 55, "max": 95, "default": 70},
        ],
    },
    "볼린저밴드": {
        "fn": bollinger_signals,
        "params": [
            {"key": "window", "label": "기간", "min": 5, "max": 60, "default": 20},
            {"key": "n_std", "label": "표준편차 배수", "min": 1.0, "max": 3.0, "default": 2.0, "step": 0.5},
        ],
    },
}
