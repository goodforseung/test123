# Quant Dashboard

퀀트 백테스트 Streamlit 대시보드. 종목을 입력해 백테스트를 실행하고, 파라미터 그리드서치를
돌리며, 결과를 Supabase에 영구 기록한다.

## 페이지

| 페이지 | 기능 |
|--------|------|
| 백테스트 실행 (`app.py`) | 종목 + **전략 선택**(이동평균/RSI/볼린저) + 비용 → 지표 + 자산곡선/Drawdown + 거래내역 + **기록 저장** |
| 그리드서치 (`pages/2_grid_search.py`) | (이동평균) fast/slow 범위 스윕 → Sharpe·수익률 히트맵 + 상위 N |
| 기록 (`pages/3_history.py`) | Supabase에 저장된 백테스트 이력 조회·삭제 |
| 팩터/포트폴리오 (`pages/4_factor.py`) | 유니버스(멀티종목) + 모멘텀/저변동성/동일비중 → 지표 + 자산곡선 |

## 전략

- **단일종목**(page 1): 이동평균 교차(추세추종), RSI·볼린저밴드(평균회귀). `quant/strategies/registry.py`에
  등록 — 새 전략 추가 시 UI 자동 갱신.
- **멀티종목 팩터**(page 4): 크로스섹셔널 모멘텀(12-1), 저변동성, 동일비중. `quant/factor.py`.

## 로컬 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 백테스트 기록 — Supabase 설정 (선택)

기록 저장/조회는 외부 DB(Supabase)가 필요하다. **미설정이어도 백테스트·그리드서치는 정상 동작**하며,
기록 기능만 비활성화된다. Streamlit Cloud는 파일시스템이 휘발성이라 영구 보존하려면 외부 DB가 필수다.

### 1) Supabase 프로젝트 + 테이블 생성
[supabase.com](https://supabase.com)에서 프로젝트를 만들고, SQL Editor에서 실행:

```sql
create table backtests (
  id bigint generated always as identity primary key,
  created_at timestamptz default now(),
  symbol text, start_date text, end_date text,
  fast int, slow int, fees float8, slippage float8,
  total_return float8, cagr float8, max_drawdown float8,
  sharpe float8, win_rate float8, num_trades int
);
```

기록에 전략·파라미터 컬럼을 추가하려면(다전략 지원), 기존 테이블에 한 번 실행:

```sql
alter table backtests add column if not exists strategy text;
alter table backtests add column if not exists params text;
```

### 2) 자격증명 입력
Project Settings → API에서 **URL**과 **anon key**를 확보한 뒤:

- **로컬**: `.streamlit/secrets.toml.example`을 `.streamlit/secrets.toml`로 복사해 채우기
- **배포(Streamlit Cloud)**: App settings → Secrets에 동일 내용 붙여넣기

```toml
[connections.supabase]
url = "https://your-project-ref.supabase.co"
key = "your-anon-public-key"
```

> `secrets.toml`은 `.gitignore`에 등록되어 커밋되지 않는다.

## 메모

- `quant/` 모듈은 메인 백테스트 프로젝트(`~/Desktop/Quant`)의 스냅샷이다. 엔진 로직 변경 시
  양쪽 동기화 필요.
