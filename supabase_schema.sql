-- 아리텍 크롤러 Supabase 테이블 생성 SQL
-- Supabase → SQL Editor 에서 실행하세요

-- 1. 사용자 테이블
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'user',  -- 'admin' 또는 'user'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. 키워드 테이블 (사용자별)
CREATE TABLE IF NOT EXISTS keywords (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    keyword TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, category, keyword)
);

-- 3. 수집 결과 테이블 (공유)
CREATE TABLE IF NOT EXISTS items (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    title TEXT,
    description TEXT,
    platform TEXT,
    query TEXT,
    query_category TEXT,
    pub_date TEXT,
    blogger_name TEXT,
    cafe_name TEXT,
    first_seen TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_items_category ON items(query_category);
CREATE INDEX IF NOT EXISTS idx_items_first_seen ON items(first_seen);
CREATE INDEX IF NOT EXISTS idx_keywords_user ON keywords(user_id);

-- 4. 기본 admin 계정 생성
-- 비밀번호: aritech2024 (SHA256 해시)
INSERT INTO users (username, password_hash, role)
VALUES ('admin', 'b96ccc2538586ac309f22cb8d79ab8b91a0901d0194cc488db784e34c08a4015', 'admin')
ON CONFLICT (username) DO NOTHING;

-- 실제 비밀번호 해시는 Python에서 생성:
-- import hashlib
-- print(hashlib.sha256("aritech2024".encode()).hexdigest())
