INSERT INTO courses (name, duration_weeks, fee_inr, description) VALUES
('Python Programming', 6, 8000, 'Python basics to OOP and file handling'),
('Machine Learning', 8, 15000, 'NumPy, pandas, scikit-learn, model evaluation'),
('AI with LangChain', 6, 18000, 'LLMs, RAG, agents, FastAPI');

INSERT INTO batches (course_id, start_date, timing, seats_left) VALUES
(1, '2026-10-12', 'Mon-Fri 9:00-11:00 AM', 12),
(2, '2026-10-19', 'Mon-Fri 5:00-7:00 PM', 8),
(3, '2026-11-02', 'Sat-Sun 10:00 AM-1:00 PM', 15);