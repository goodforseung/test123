"""Quant 백테스트 대시보드 — 페이지 1: 백테스트 실행 & 성과."""
from __future__ import annotations

import json

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from quant.data import get_price
from quant.strategies import SINGLE_STRATEGIES
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

    # 전략 선택 + 선택 전략의 파라미터 동적 렌더 (registry 기반)
    strategy_name = st.selectbox("전략", list(SINGLE_STRATEGIES.keys()))
    spec = SINGLE_STRATEGIES[strategy_name]
    params: dict = {}
    for p in spec["params"]:
        if isinstance(p["default"], float) or "step" in p:
            params[p["key"]] = st.slider(
                p["label"], float(p["min"]), float(p["max"]),
                float(p["default"]), step=float(p.get("step", 0.1)),
            )
        else:
            params[p["key"]] = st.slider(
                p["label"], int(p["min"]), int(p["max"]), int(p["default"])
            )

    fees = st.number_input("수수료율 (편도)", value=0.00015, format="%.5f", step=0.00005)
    slippage = st.number_input("슬리피지율", value=0.001, format="%.4f", step=0.0005)
    run_bt = st.button("백테스트 실행", type="primary", use_container_width=True)


# ── 캐싱 함수 ───────────────────────────────────────────────────
@st.cache_data(show_spinner="데이터 수집 중...")
def fetch_price(symbol: str, start: str, end: str) -> pd.DataFrame:
    return get_price(symbol, start, end)


@st.cache_data(show_spinner="백테스트 실행 중...")
def run_backtest(
    _close_values: list,   # 언더스코어=캐시키 제외(대용량). 데이터 식별은 아래 symbol/start/end로
    _close_index: list,
    symbol: str,           # ↓ 캐시 키: 종목·기간이 바뀌면 재계산되도록 반드시 포함
    start: str,
    end: str,
    strategy_name: str,
    params_json: str,      # 캐시 키로 쓰기 위해 JSON 문자열로 받음
    fees: float,
    slippage: float,
):
    """캐싱을 위해 close를 list로 받아 내부에서 Series로 복원.

    주의: _close_values/_close_index는 언더스코어라 st.cache_data가 해시하지 않는다.
    따라서 데이터를 식별하는 symbol/start/end를 캐시 키에 포함해야 기간 변경이 반영된다.
    """
    close = pd.Series(_close_values, index=pd.DatetimeIndex(_close_index), name="Close")
    params = json.loads(params_json)
    fn = SINGLE_STRATEGIES[strategy_name]["fn"]
    entries, exits = fn(close, **params)
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
    # 이동평균 교차일 때만 fast<slow 가드
    if strategy_name == "이동평균 교차" and params.get("fast", 0) >= params.get("slow", 1):
        st.error("Fast MA는 Slow MA보다 작아야 합니다.")
        st.stop()

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    price_df = fetch_price(symbol, start_str, end_str)
    if price_df.empty:
        st.error("데이터를 가져올 수 없습니다. 종목 코드를 확인하세요.")
        st.stop()

    close = price_df["Close"]
    params_json = json.dumps(params, sort_keys=True)
    stats, equity, drawdown, trades_df = run_backtest(
        close.values.tolist(),
        close.index.tolist(),
        symbol, start_str, end_str,
        strategy_name, params_json, fees, slippage,
    )

    # 파라미터를 "fast=20, slow=60" 형태로 보기 좋게
    params_label = ", ".join(f"{k}={v}" for k, v in params.items())
    st.session_state["result"] = {
        "stats": stats, "equity": equity, "drawdown": drawdown, "trades": trades_df,
        "symbol": symbol, "strategy": strategy_name, "params_label": params_label,
        "start": start_str, "end": end_str,
        # DB 적재용 record (lib.history.COLUMNS와 매핑)
        "record": {
            "strategy": strategy_name, "symbol": symbol,
            "start_date": start_str, "end_date": end_str,
            "fees": fees, "slippage": slippage, "params": params_json,
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

    st.subheader(f"{res['symbol']} — {res['strategy']} ({res['params_label']}) 백테스트 결과")
    st.caption(f"📅 이 결과의 기간: {res['start']} ~ {res['end']}  ·  "
               f"사이드바 설정을 바꾸면 **'백테스트 실행'을 다시 눌러야** 갱신됩니다.")
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
