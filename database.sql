DROP TABLE IF EXISTS messages, conversations, users CASCADE;

CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  email TEXT UNIQUE,
  password TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  is_verified BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS conversations (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT,
  started_at TIMESTAMP DEFAULT NOW(),
  last_update TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
  id SERIAL PRIMARY KEY,
  conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user','assistant', 'file')),
  content TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

ALTER TABLE langchain_pg_embedding
  ADD COLUMN tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('french', document)) STORED;
CREATE INDEX idx_chunks_tsv ON langchain_pg_embedding USING GIN(tsv);