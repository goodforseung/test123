"""데이터 수집 모듈.

한국/미국 주식 가격 데이터를 통일된 형태(OHLCV)로 가져오고,
로컬 parquet 캐시에 저장해 재요청 시 네트워크 없이 읽는다.

의존성: FinanceDataReader(메인), pykrx(한국 보조), yfinance(미국 보조)
"""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import FinanceDataReader as fdr

# 캐시 디렉터리: 프로젝트 루트의 data/cache
_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cache")
os.makedirs(_CACHE_DIR, exist_ok=True)

# 표준 컬럼: 어떤 소스든 이 형태로 맞춘다
_OHLCV = ["Open", "High", "Low", "Close", "Volume"]


def _cache_path(symbol: str, start: str, end: str) -> str:
    key = f"{symbol}_{start}_{end}".replace("/", "-")
    return os.path.join(_CACHE_DIR, f"{key}.parquet")


def get_price(
    symbol: str,
    start: str = "2015-01-01",
    end: str | None = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """단일 종목의 일봉 OHLCV를 가져온다.

    Args:
        symbol: 한국은 6자리 코드("005930"), 미국은 티커("AAPL").
        start, end: "YYYY-MM-DD". end가 None이면 오늘까지.
        use_cache: True면 로컬 parquet 캐시 우선 사용.

    Returns:
        DatetimeIndex에 [Open, High, Low, Close, Volume] 컬럼을 가진 DataFrame.
    """
    end = end or datetime.today().strftime("%Y-%m-%d")
    path = _cache_path(symbol, start, end)

    if use_cache and os.path.exists(path):
        return pd.read_parquet(path)

    df = fdr.DataReader(symbol, start, end)
    # FDR은 소스에 따라 컬럼이 조금씩 다름 → 표준 OHLCV만 추림
    df = df[[c for c in _OHLCV if c in df.columns]].copy()
    df.index.name = "Date"

    if use_cache:
        df.to_parquet(path)
    return df


def get_prices(
    symbols: list[str],
    start: str = "2015-01-01",
    end: str | None = None,
    field: str = "Close",
    use_cache: bool = True,
) -> pd.DataFrame:
    """여러 종목의 특정 필드(기본 종가)를 한 DataFrame으로 합친다.

    Returns:
        index=Date, columns=symbol 형태의 wide DataFrame.
    """
    cols = {}
    for sym in symbols:
        s = get_price(sym, start, end, use_cache)[field]
        s.name = sym
        cols[sym] = s
    return pd.DataFrame(cols).dropna(how="all")


def krx_listing(market: str = "KOSPI") -> pd.DataFrame:
    """한국 상장 종목 목록. market: KOSPI / KOSDAQ / KRX."""
    return fdr.StockListing(market)


def us_listing(market: str = "S&P500") -> pd.DataFrame:
    """미국 종목 목록. market: S&P500 / NASDAQ / NYSE."""
    return fdr.StockListing(market)


if __name__ == "__main__":
    # 빠른 동작 확인: 삼성전자 + 애플
    samsung = get_price("005930", "2024-01-01")
    apple = get_price("AAPL", "2024-01-01")
    print("삼성전자:", samsung.shape, "| 최근 종가:", int(samsung["Close"].iloc[-1]))
    print("애플:", apple.shape, "| 최근 종가:", round(apple["Close"].iloc[-1], 2))

    both = get_prices(["005930", "AAPL"], "2024-01-01")
    print("\n합본 데이터 tail:")
    print(both.tail(3))
