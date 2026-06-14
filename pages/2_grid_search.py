"""페이지 2: 파라미터 그리드서치."""
from __future__ import annotations

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

from quant.data import get_price
from quant import optimize

st.set_page_config(page_title="Grid Search", page_icon="🔍", layout="wide")
st.title("파라미터 그리드서치")

# ── 사이드바 ────────────────────────────────────────────────────
with st.sidebar:
    st.header("그리드서치 설정")
    symbol = st.text_input("종목 코드", value="005930", key="gs_symbol")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("시작일", value=pd.Timestamp("2018-01-01"), key="gs_start")
    with col2:
        end_date = st.date_input("종료일", value=pd.Timestamp.today(), key="gs_end")

    fees = st.number_input("수수료율 (편도)", value=0.00015, format="%.5f", step=0.00005, key="gs_fees")

    st.subheader("Fast MA 범위")
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        fast_min = st.number_input("min", value=5, min_value=2, key="f_min")
    with fc2:
        fast_max = st.number_input("max", value=50, min_value=3, key="f_max")
    with fc3:
        fast_step = st.number_input("step", value=5, min_value=1, key="f_step")

    st.subheader("Slow MA 범위")
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        slow_min = st.number_input("min", value=20, min_value=5, key="s_min")
    with sc2:
        slow_max = st.number_input("max", value=200, min_value=10, key="s_max")
    with sc3:
        slow_step = st.number_input("step", value=10, min_value=1, key="s_step")

    top_n = st.slider("상위 N개 표시", min_value=3, max_value=20, value=10)
    run_gs = st.button("그리드서치 실행", type="primary", use_container_width=True)


@st.cache_data(show_spinner="데이터 수집 중...")
def fetch_price(symbol: str, start: str, end: str) -> pd.DataFrame:
    return get_price(symbol, start, end)


@st.cache_data(show_spinner="그리드서치 실행 중... (시간이 걸릴 수 있습니다)")
def run_grid(
    _close_values: list,   # 언더스코어=캐시키 제외. 데이터 식별은 symbol/start/end로
    _close_index: list,
    symbol: str,           # ↓ 캐시 키: 종목·기간 변경 시 재계산되도록 포함
    start: str,
    end: str,
    fasts: list[int],
    slows: list[int],
    fees: float,
) -> pd.DataFrame:
    close = pd.Series(_close_values, index=pd.DatetimeIndex(_close_index), name="Close")
    return optimize.grid_search(close, fasts, slows, fees=fees)


# ── 메인 영역 ───────────────────────────────────────────────────
if run_gs:
    fasts = list(range(int(fast_min), int(fast_max) + 1, int(fast_step)))
    slows = list(range(int(slow_min), int(slow_max) + 1, int(slow_step)))

    if not fasts or not slows:
        st.error("범위 설정이 잘못되었습니다.")
        st.stop()

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    price_df = fetch_price(symbol, start_str, end_str)
    if price_df.empty:
        st.error("데이터를 가져올 수 없습니다.")
        st.stop()

    close = price_df["Close"]
    results = run_grid(
        close.values.tolist(), close.index.tolist(),
        symbol, start_str, end_str,
        fasts, slows, fees,
    )

    st.subheader(f"{symbol} — 그리드서치 결과 (총 {len(results)}개 조합)")

    # 히트맵 생성 함수
    def make_heatmap(results: pd.DataFrame, metric: str, title: str):
        grid = results[metric].unstack("slow")
        fig = px.imshow(
            grid.values,
            x=[str(c) for c in grid.columns],
            y=[str(i) for i in grid.index],
            labels=dict(x="Slow MA", y="Fast MA", color=metric),
            color_continuous_scale="Viridis",
            aspect="auto",
        )
        fig.update_layout(title=title, height=500)
        return fig

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(
            make_heatmap(results, "sharpe", "Sharpe Ratio Heatmap"),
            use_container_width=True,
        )
    with col2:
        st.plotly_chart(
            make_heatmap(results, "total_return", "Total Return Heatmap"),
            use_container_width=True,
        )

    # 상위 N개 파라미터 테이블
    st.subheader(f"상위 {top_n}개 파라미터 (Sharpe 기준)")
    top = results.head(top_n).reset_index()
    top["sharpe"] = top["sharpe"].map(lambda x: f"{x:.2f}" if pd.notna(x) else "N/A")
    top["total_return"] = top["total_return"].map(lambda x: f"{x:+.2%}")
    top["max_drawdown"] = top["max_drawdown"].map(lambda x: f"{x:.2%}")
    top["num_trades"] = top["num_trades"].astype(int)
    st.dataframe(top, use_container_width=True, hide_index=True)
else:
    st.info("사이드바에서 설정 후 '그리드서치 실행' 버튼을 누르세요.")
