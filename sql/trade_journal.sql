-- 자동매매 저널 미러 테이블 (원본은 로컬 JSONL — 이 테이블은 조회용 복사본)
-- Supabase SQL Editor에서 1회 실행
create table if not exists trade_journal (
  id          bigint generated always as identity primary key,
  event_key   text unique not null,        -- 이벤트 해시(멱등 업서트 키)
  ts          timestamptz not null,
  run_id      text not null,
  event       text not null,               -- run_start / skip / order_attempt / order_result / ...
  mode        text,                        -- real | paper
  dry_run     boolean,
  symbol      text,
  side        text,                        -- buy | sell
  qty         integer,
  ref_price   numeric,
  signal_date date,
  reason      text,                        -- 스킵 사유
  rt_cd       text,                        -- KIS 응답 코드("0"=접수)
  payload     jsonb not null,              -- 원본 이벤트 전체
  created_at  timestamptz not null default now()
);

create index if not exists idx_trade_journal_ts on trade_journal (ts desc);
create index if not exists idx_trade_journal_event on trade_journal (event);
