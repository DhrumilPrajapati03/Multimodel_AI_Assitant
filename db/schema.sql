CREATE TABLE courses (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    duration_weeks INT NOT NULL,
    fee_inr INT NOT NULL,
    description TEXT
);

CREATE TABLE batches (
    id SERIAL PRIMARY KEY,
    course_id INT NOT NULL REFERENCES courses(id),
    start_date DATE NOT NULL,
    timing TEXT NOT NULL,
    seats_left INT NOT NULL
);

CREATE TABLE chat_history (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    message TEXT NOT NULL,
    intent TEXT,
    channel TEXT CHECK (channel IN ('text', 'voice')),
    created_at TIMESTAMPTZ DEFAULT now()
);