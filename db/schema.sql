-- Safe to run on every start: creates what's missing, never drops data.

CREATE TABLE IF NOT EXISTS courses (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    duration_weeks INT NOT NULL,
    fee_inr INT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS batches (
    id SERIAL PRIMARY KEY,
    course_id INT NOT NULL REFERENCES courses(id),
    start_date DATE NOT NULL,
    timing TEXT NOT NULL,
    seats_left INT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_history (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    message TEXT NOT NULL,
    intent TEXT,
    channel TEXT CHECK (channel IN ('text', 'voice')),
    created_at TIMESTAMPTZ DEFAULT now()
);
-- What an attached image showed (from the vision model), so later turns remember it.
ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS image_note TEXT;
-- Language Whisper detected for voice messages (e.g. "Hindi").
ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS language TEXT;
-- Database rows behind an answer, so its table/chart can be redrawn when the chat is reopened.
ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS data JSONB;
CREATE INDEX IF NOT EXISTS chat_history_session_idx ON chat_history (session_id, created_at);

-- Knowledge base: documents and their embedded chunks (searched in memory by the app).
-- Development builds stored vectors as REAL[]; rebuild those tables (bundled PDFs re-index on start).
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'doc_chunks' AND column_name = 'embedding' AND data_type = 'ARRAY') THEN
        DROP TABLE doc_chunks;
        DELETE FROM documents;
    END IF;
END $$;
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('pdf', 'text', 'image')),
    source TEXT NOT NULL DEFAULT 'upload' CHECK (source IN ('seed', 'upload')),
    status TEXT NOT NULL DEFAULT 'processing' CHECK (status IN ('processing', 'ready', 'failed')),
    chunks INT NOT NULL DEFAULT 0,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS doc_chunks (
    id SERIAL PRIMARY KEY,
    document_id INT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page INT,
    content TEXT NOT NULL,
    embedding BYTEA NOT NULL      -- 384 float32 values; raw bytes load ~20x faster than REAL[]
);
CREATE INDEX IF NOT EXISTS doc_chunks_document_idx ON doc_chunks (document_id);

-- Enquiries / enrollment requests collected by the assistant.
CREATE TABLE IF NOT EXISTS leads (
    id SERIAL PRIMARY KEY,
    session_id TEXT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT,
    course TEXT,
    message TEXT,
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'contacted', 'closed')),
    created_at TIMESTAMPTZ DEFAULT now()
);
