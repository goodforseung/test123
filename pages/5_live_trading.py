"""페이지 5: 자동매매 기록 (읽기 전용 — 원본은 메인 프로젝트의 로컬 저널)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from lib import live_journal
from lib.history import is_configured

st.set_page_config(page_title="Live Trading", page_icon="🤖", layout="wide")
st.title("자동매매 기록")
st.caption("매 거래일 아침 신호→주문 루프의 저널 미러입니다. 원본은 로컬 JSONL — 여기서는 조회만.")

if not is_configured():
    st.warning("Supabase가 설정되지 않았습니다. (백테스트 기록과 동일한 시크릿을 사용합니다)")
    st.stop()

if st.button("새로고침"):
    st.rerun()

# ── 오늘의 리포트 (최신 daily_report) ────────────────────────
payload = live_journal.load_latest_report()
if payload:
    rep = payload.get("report") or {}
    st.subheader("오늘의 리포트")
    st.caption(payload.get("summary_text", ""))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("날짜 · 모드", f"{rep.get('date', '?')} {'🟢 드라이런' if rep.get('dry_run') else '🔴 실전송'}")
    cash = (rep.get("balance") or {}).get("cash")
    c2.metric("예수금", f"{cash:,}원" if isinstance(cash, (int, float)) else "?")
    c3.metric("주문", f"{len(rep.get('orders') or [])}건")
    c4.metric("스킵 / 에러",
              f"{sum((rep.get('skips') or {}).values())} / {len(rep.get('errors') or [])}")

    sigs = rep.get("signals") or []
    if sigs:
        sdf = pd.DataFrame(sigs)
        if "name" in sdf.columns:  # "카카오(035720)" 표기
            sdf["symbol"] = sdf.apply(
                lambda r: f"{r['name']}({r['symbol']})" if r.get("name") else r["symbol"], axis=1)
        # 트리거는 내일 하루 기준 경계값 — 도달 불가능(±30% 밖)이면 표시 생략
        if "trigger_pct" in sdf.columns:
            far = sdf["trigger_pct"].isna() | (sdf["trigger_pct"].abs() > 30) | (sdf.get("trigger", 0) <= 0)
            sdf.loc[far, ["trigger", "trigger_pct"]] = None
        sdf = sdf.rename(columns={
            "symbol": "종목", "close": "종가", "ma_fast": "MA단기", "ma_slow": "MA장기",
            "gap_pct": "갭%", "trigger": "트리거가", "trigger_pct": "트리거%",
            "held_qty": "보유", "signal_date": "신호일"})
        sdf = sdf[[c for c in ["종목", "종가", "갭%", "트리거가", "트리거%",
                               "MA단기", "MA장기", "보유", "신호일"] if c in sdf.columns]]
        st.caption("갭% = (MA단기−MA장기)/MA장기 — 0 근접 = 크로스 임박 · "
                   "트리거가 = 다음 종가가 이 값을 넘으면(갭<0) 골든크로스 / 깨지면(갭>0) 데드크로스")
        st.dataframe(
            sdf.style.background_gradient(subset=["갭%"], cmap="RdYlGn", vmin=-15, vmax=15),
            use_container_width=True, hide_index=True)

    uni = rep.get("universe") or {}
    if uni.get("added") or uni.get("removed"):
        with st.expander(f"🔄 유니버스 변경 (기준일 {uni.get('as_of')})", expanded=True):
            if uni.get("added"):
                st.write("**추가**:", ", ".join(uni["added"]))
            if uni.get("removed"):
                st.write("**제외**:", ", ".join(uni["removed"]))
    if uni.get("error"):
        st.warning(f"유니버스 갱신 실패(기존 유지): {uni['error']}")
    st.divider()

# ── 가상 포트폴리오 ("라이브였다면" 성과) ────────────────────
virt = live_journal.load_latest_virtual()
if virt:
    st.subheader("가상 포트폴리오 — 라이브였다면")
    st.caption("드라이런 신호를 가상 체결(시가 + 수수료·슬리피지)한 성과. "
               "실제 주문과 무관한 시뮬레이션입니다.")
    v1, v2, v3, v4 = st.columns(4)
    v1.metric("가상 자산", f"{virt.get('equity', 0):,}원",
              f"{virt.get('total_return', 0):+.2%}")
    v2.metric("초기 자본", f"{virt.get('init_cash', 0):,}원")
    v3.metric("거래 횟수", f"{virt.get('n_trades', 0)}회")
    v4.metric("MDD", f"{virt.get('max_drawdown', 0):.1%}")
    curve = virt.get("curve") or []
    if len(curve) > 1:
        cdf = pd.DataFrame(curve, columns=["날짜", "가상자산"]).set_index("날짜")
        st.line_chart(cdf, height=240)
    else:
        st.info("아직 가상 거래가 없어 곡선이 평평합니다 — 첫 신호가 나면 그려집니다.")
    holdings = virt.get("holdings") or {}
    if holdings:
        st.caption("가상 보유: " + ", ".join(f"{s} {q}주" for s, q in holdings.items()))
    st.divider()

df = live_journal.load_journal()
if df.empty:
    st.info("아직 미러된 기록이 없습니다. 루프가 실행되면 자동으로 쌓입니다.")
    st.stop()

df["ts"] = pd.to_datetime(df["ts"])

# ── 최근 실행 요약 ────────────────────────────────────────────
runs = df[df["event"] == "run_end"].sort_values("ts", ascending=False)
last_start = df[df["event"] == "run_start"].sort_values("ts", ascending=False)
c1, c2, c3, c4 = st.columns(4)
c1.metric("총 이벤트", f"{len(df)}건")
c2.metric("실행 횟수", f"{len(runs)}회")
if not last_start.empty:
    last = last_start.iloc[0]
    mode = "🟢 드라이런" if last.get("dry_run") else "🔴 실전송"
    c3.metric("마지막 실행", last["ts"].strftime("%m/%d %H:%M"))
    c4.metric("모드", mode)

# ── 매수/매도 내역 (핵심 뷰) ──────────────────────────────────
st.subheader("매수 · 매도 내역")
orders = df[df["event"] == "order_result"].copy()
if orders.empty:
    st.info("아직 주문(드라이런 포함)이 없습니다 — 신호가 나면 여기에 표시됩니다.")
else:
    orders["구분"] = orders["dry_run"].map({True: "드라이런", False: "실전송"})
    orders["결과"] = orders.apply(
        lambda r: "전송 안 됨" if r["dry_run"]
        else ("✅ 접수" if str(r.get("rt_cd")) == "0" else f"❌ 거부"), axis=1)
    view = orders[["ts", "구분", "symbol", "side", "qty", "ref_price", "signal_date", "결과"]]
    view = view.rename(columns={"ts": "시각", "symbol": "종목", "side": "방향",
                                "qty": "수량", "ref_price": "기준가", "signal_date": "신호일"})
    st.dataframe(view, use_container_width=True, hide_index=True)

# ── 스킵/홀드 사유 분포 ──────────────────────────────────────
st.subheader("스킵 · 홀드 사유")
skips = df[df["event"] == "skip"]
if not skips.empty:
    st.bar_chart(skips["reason"].value_counts())

# ── 전체 이벤트 (필터) ────────────────────────────────────────
st.subheader("전체 이벤트")
kinds = sorted(df["event"].dropna().unique())
sel = st.multiselect("이벤트 종류", kinds, default=kinds)
full = df[df["event"].isin(sel)]
cols = [c for c in ["ts", "event", "mode", "dry_run", "symbol", "side", "qty",
                    "ref_price", "signal_date", "reason", "rt_cd", "run_id"] if c in full.columns]
st.dataframe(full[cols], use_container_width=True, hide_index=True, height=400)
