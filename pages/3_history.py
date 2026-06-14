"""페이지 3: 백테스트 기록 (Supabase 영속 저장)."""
from __future__ import annotations

import streamlit as st

from lib import history

st.set_page_config(page_title="History", page_icon="🗂️", layout="wide")
st.title("백테스트 기록")

if not history.is_configured():
    st.warning("Supabase가 설정되지 않았습니다. 기록을 저장·조회하려면 설정이 필요합니다.")
    st.markdown(
        """
        **설정 방법**
        1. [supabase.com](https://supabase.com)에서 새 프로젝트 생성
        2. SQL Editor에서 `backtests` 테이블 생성 (README 참고)
        3. Project Settings → API에서 **URL**과 **anon key** 확보
        4. `.streamlit/secrets.toml`(로컬) 또는 Streamlit Cloud Secrets에 입력:
        ```toml
        [connections.supabase]
        url = "https://xxxx.supabase.co"
        key = "your-anon-key"
        ```
        """
    )
    st.stop()

# ── 컨트롤 ──────────────────────────────────────────────────────
col1, col2 = st.columns([1, 5])
with col1:
    if st.button("새로고침", use_container_width=True):
        st.rerun()

df = history.load_history()

if df.empty:
    st.info("아직 저장된 기록이 없습니다. 백테스트 실행 후 '기록 저장'을 눌러보세요.")
    st.stop()

st.caption(f"총 {len(df)}건")

# 보기 좋게 포맷 (퍼센트 지표)
view = df.copy()
for col, fmt in {
    "total_return": "{:+.2%}", "cagr": "{:+.2%}", "max_drawdown": "{:.2%}",
    "win_rate": "{:.2%}", "sharpe": "{:.2f}", "fees": "{:.5f}", "slippage": "{:.4f}",
}.items():
    if col in view.columns:
        view[col] = view[col].map(lambda x, f=fmt: f.format(x) if x is not None else "")

# 컬럼 순서/이름 정리
order = ["created_at", "symbol", "start_date", "end_date", "fast", "slow",
         "total_return", "cagr", "max_drawdown", "sharpe", "win_rate", "num_trades",
         "fees", "slippage"]
view = view[[c for c in order if c in view.columns]]
st.dataframe(view, use_container_width=True, hide_index=True, height=500)

# ── 전체 삭제 (확인 절차) ────────────────────────────────────────
with st.expander("⚠️ 전체 기록 삭제"):
    st.write("모든 기록을 영구 삭제합니다. 되돌릴 수 없습니다.")
    if st.checkbox("삭제를 확인합니다"):
        if st.button("전체 삭제 실행", type="primary"):
            ok, msg = history.clear_history()
            (st.success if ok else st.error)(msg)
            if ok:
                st.rerun()
