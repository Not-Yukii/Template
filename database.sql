DROP TABLE IF EXISTS memories, messages, conversations, users CASCADE;

CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  email TEXT UNIQUE,
  password TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
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
  role TEXT NOT NULL CHECK (role IN ('user','assistant')),
  content TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS memories (
  id SERIAL PRIMARY KEY,
  message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  embedding VECTOR(384) NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Index pour accélérer la recherche (flat ou ivfflat)
--   a) Index simple (vector_l2_ops)
CREATE INDEX IF NOT EXISTS idx_memories_embedding_flat
  ON memories USING ivfflat (embedding vector_l2_ops)
  WITH (lists = 100);

-- Note : pour ivfflat, après avoir inséré des lignes, vous devez exécuter :
--   ALTER INDEX idx_memories_embedding_flat REINDEX;
-- Sinon, utilisez simplement vector_l2_ops (flat) sans ivfflat :
-- CREATE INDEX idx_memories_embedding_flat ON memories USING vector_l2_ops (embedding);