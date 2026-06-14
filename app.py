"""Quant 백테스트 대시보드 — 페이지 1: 백테스트 실행 & 성과."""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from quant.data import get_price
from quant.strategies import ma_cross_signals
from quant import engine, analysis
from lib import history

st.set_page_config(page_title="Quant Dashboard", page_icon="📈", layout="wide")
st.title("백테스트 실행 & 성과")

# ── 사이드바: 입력 ──────────────────────────────────────────────
with st.sidebar:
    st.header("파라미터 설정")
    symbol = st.text_input("종목 코드", value="005930", help="한국: 005930 / 미국: AAPL")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("시작일", value=pd.Timestamp("2018-01-01"))
    with col2:
        end_date = st.date_input("종료일", value=pd.Timestamp.today())

    fast = st.slider("Fast MA", min_value=3, max_value=100, value=20)
    slow = st.slider("Slow MA", min_value=10, max_value=300, value=60)
    fees = st.number_input("수수료율 (편도)", value=0.00015, format="%.5f", step=0.00005)
    slippage = st.number_input("슬리피지율", value=0.001, format="%.4f", step=0.0005)
    run_bt = st.button("백테스트 실행", type="primary", use_container_width=True)


# ── 캐싱 함수 ───────────────────────────────────────────────────
@st.cache_data(show_spinner="데이터 수집 중...")
def fetch_price(symbol: str, start: str, end: str) -> pd.DataFrame:
    return get_price(symbol, start, end)


@st.cache_data(show_spinner="백테스트 실행 중...")
def run_backtest(
    _close_values: list,
    _close_index: list,
    fast: int,
    slow: int,
    fees: float,
    slippage: float,
):
    """캐싱을 위해 close를 list로 받아 내부에서 Series로 복원."""
    close = pd.Series(_close_values, index=pd.DatetimeIndex(_close_index), name="Close")
    entries, exits = ma_cross_signals(close, fast=fast, slow=slow)
    pf = engine.run(close, entries, exits, fees=fees, slippage=slippage)
    stats = analysis.summary(pf)
    equity = pf.value()
    drawdown = pf.drawdown()

    # 거래 내역 추출
    trades_df = pd.DataFrame()
    if pf.trades.count() > 0:
        rec = pf.trades.records_readable
        trades_df = rec[["Entry Timestamp", "Exit Timestamp", "PnL", "Return", "Direction", "Status"]].copy()
        trades_df.columns = ["진입일", "청산일", "손익", "수익률", "방향", "상태"]

    return stats, equity, drawdown, trades_df


# ── 백테스트 실행 → 결과를 session_state에 저장 ──────────────────
# (저장 버튼 클릭 시 앱이 재실행되어도 결과가 유지되도록 session_state에 보관)
if run_bt:
    if fast >= slow:
        st.error("Fast MA는 Slow MA보다 작아야 합니다.")
        st.stop()

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    price_df = fetch_price(symbol, start_str, end_str)
    if price_df.empty:
        st.error("데이터를 가져올 수 없습니다. 종목 코드를 확인하세요.")
        st.stop()

    close = price_df["Close"]
    stats, equity, drawdown, trades_df = run_backtest(
        close.values.tolist(),
        close.index.tolist(),
        fast, slow, fees, slippage,
    )

    st.session_state["result"] = {
        "stats": stats, "equity": equity, "drawdown": drawdown, "trades": trades_df,
        "symbol": symbol, "fast": fast, "slow": slow,
        # DB 적재용 record (lib.history.COLUMNS와 매핑)
        "record": {
            "symbol": symbol, "start_date": start_str, "end_date": end_str,
            "fast": fast, "slow": slow, "fees": fees, "slippage": slippage,
            **stats,
        },
    }


def _save_result():
    """저장 버튼 콜백 — session_state의 record를 Supabase에 적재."""
    ok, msg = history.save_backtest(st.session_state["result"]["record"])
    st.session_state["save_msg"] = (ok, msg)


# ── 결과 렌더링 (session_state에 결과가 있으면) ──────────────────
res = st.session_state.get("result")
if res:
    stats, equity, drawdown, trades_df = res["stats"], res["equity"], res["drawdown"], res["trades"]

    st.subheader(f"{res['symbol']} — MA({res['fast']}/{res['slow']}) 백테스트 결과")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("누적수익률", f"{stats['total_return']:+.2%}")
    c2.metric("CAGR", f"{stats['cagr']:+.2%}")
    c3.metric("MDD", f"{stats['max_drawdown']:.2%}")
    c4.metric("샤프지수", f"{stats['sharpe']:.2f}")
    c5.metric("승률", f"{stats['win_rate']:.2%}")
    c6.metric("거래횟수", f"{stats['num_trades']}")

    # 기록 저장 버튼 (Supabase 미설정 시 안내)
    if history.is_configured():
        st.button("📌 이 결과 기록 저장", on_click=_save_result)
    else:
        st.caption("ℹ️ 기록 저장은 Supabase 설정 후 가능합니다 (.streamlit/secrets.toml).")
    if "save_msg" in st.session_state:
        ok, msg = st.session_state.pop("save_msg")
        (st.success if ok else st.error)(msg)

    # 자산곡선 차트
    fig_eq = go.Figure()
    fig_eq.add_trace(go.Scatter(x=equity.index, y=equity.values, mode="lines", name="Portfolio Value"))
    fig_eq.update_layout(title="자산 곡선 (Equity Curve)", xaxis_title="Date", yaxis_title="Value", height=400)
    st.plotly_chart(fig_eq, use_container_width=True)

    # Drawdown 차트
    fig_dd = go.Figure()
    fig_dd.add_trace(go.Scatter(
        x=drawdown.index, y=drawdown.values, mode="lines",
        fill="tozeroy", name="Drawdown", line=dict(color="crimson"),
    ))
    fig_dd.update_layout(title="Drawdown", xaxis_title="Date", yaxis_title="Drawdown", height=300)
    fig_dd.update_yaxes(tickformat=".1%")
    st.plotly_chart(fig_dd, use_container_width=True)

    # 거래 내역 테이블
    st.subheader("거래 내역")
    if not trades_df.empty:
        display_df = trades_df.copy()
        display_df["수익률"] = display_df["수익률"].map(lambda x: f"{x:+.2%}")
        display_df["손익"] = display_df["손익"].map(lambda x: f"{x:+,.0f}")
        st.dataframe(display_df, use_container_width=True, height=400)
    else:
        st.info("거래 내역이 없습니다.")
else:
    st.info("사이드바에서 파라미터를 설정하고 '백테스트 실행' 버튼을 누르세요.")
