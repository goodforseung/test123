"""페이지 4: 팩터 / 포트폴리오 (멀티종목).

여러 종목(유니버스)을 입력하고, 크로스섹셔널 전략(모멘텀·저변동성) 또는 동일비중으로
포트폴리오를 굴린다. 단일종목 백테스트(page 1)와 달리 '종목 간 상대 비교'다.
"""
from __future__ import annotations

import json

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from quant.data import get_prices
from quant import factor, analysis
from lib import history

st.set_page_config(page_title="Factor / Portfolio", page_icon="🧩", layout="wide")
st.title("팩터 / 포트폴리오 (멀티종목)")

KINDS = {"모멘텀": "momentum", "저변동성": "low_vol", "동일비중": "equal"}

with st.sidebar:
    st.header("설정")
    universe_text = st.text_area(
        "유니버스 (종목코드, 쉼표/공백/줄바꿈 구분)",
        value="005930, 000660, 035420, 005380, 051910, 006400, 035720, 068270, 105560, 055550",
        height=120,
    )
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("시작일", value=pd.Timestamp("2018-01-01"))
    with col2:
        end_date = st.date_input("종료일", value=pd.Timestamp.today())

    kind_label = st.selectbox("전략", list(KINDS.keys()))
    q = st.slider("상위 분위 (선택 비율)", 0.1, 1.0, 0.2, step=0.1,
                  help="모멘텀/저변동성에만 적용. 0.2 = 상위 20% 매수")
    rebalance = st.selectbox("리밸런싱 주기", ["M", "W"], format_func=lambda x: {"M": "월간", "W": "주간"}[x])
    fees = st.number_input("수수료율 (편도)", value=0.00015, format="%.5f", step=0.00005)
    run = st.button("실행", type="primary", use_container_width=True)


@st.cache_data(show_spinner="데이터 수집 중...")
def fetch(symbols: tuple, start: str, end: str) -> pd.DataFrame:
    return get_prices(list(symbols), start, end)


def _save():
    ok, msg = history.save_backtest(st.session_state["factor_result"]["record"])
    st.session_state["factor_save_msg"] = (ok, msg)


if run:
    symbols = [s.strip() for s in universe_text.replace(",", " ").split() if s.strip()]
    if len(symbols) < 2:
        st.error("종목을 2개 이상 입력하세요.")
        st.stop()

    start_str, end_str = start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
    close_df = fetch(tuple(symbols), start_str, end_str)
    close_df = close_df.dropna(how="all").ffill()
    if close_df.empty or close_df.shape[1] < 2:
        st.error("데이터를 가져오지 못했습니다. 종목코드를 확인하세요.")
        st.stop()

    kind = KINDS[kind_label]
    with st.spinner("백테스트 실행 중..."):
        pf = factor.run_factor(close_df, kind=kind, q=q, rebalance=rebalance, fees=fees)
        stats = analysis.summary(pf)
        equity = pf.value()

    n = close_df.shape[1]
    st.session_state["factor_result"] = {
        "stats": stats, "equity": equity, "kind_label": kind_label, "n": n,
        "record": {
            "strategy": kind_label, "symbol": f"{kind_label} 유니버스({n})",
            "start_date": start_str, "end_date": end_str,
            "fees": fees, "slippage": 0.001,
            "params": json.dumps({"q": q, "rebalance": rebalance, "n": n}, sort_keys=True),
            **stats,
        },
    }


res = st.session_state.get("factor_result")
if res:
    stats = res["stats"]
    st.subheader(f"{res['kind_label']} — {res['n']}종목 포트폴리오")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("누적수익률", f"{stats['total_return']:+.2%}")
    c2.metric("CAGR", f"{stats['cagr']:+.2%}")
    c3.metric("MDD", f"{stats['max_drawdown']:.2%}")
    c4.metric("샤프지수", f"{stats['sharpe']:.2f}")

    if history.is_configured():
        st.button("📌 이 결과 기록 저장", on_click=_save)
    if "factor_save_msg" in st.session_state:
        ok, msg = st.session_state.pop("factor_save_msg")
        (st.success if ok else st.error)(msg)

    equity = res["equity"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=equity.index, y=equity.values, mode="lines", name="Portfolio Value"))
    fig.update_layout(title="자산 곡선", xaxis_title="Date", yaxis_title="Value", height=420)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("사이드바에서 유니버스·전략을 설정하고 '실행'을 누르세요.")
