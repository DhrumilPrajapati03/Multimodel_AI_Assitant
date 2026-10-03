from langchain.agents import create_agent
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import InMemorySaver

from config import MODEL_NAME
from tools.rag import search_academy_docs
from tools.sql_tool import query_academy_db

llm = ChatGroq(model=MODEL_NAME, temperature=0.3, reasoning_effort="low")

SYSTEM_PROMPT = """You are the helpdesk assistant for our computer academy.
- Use search_academy_docs for syllabus, course content and policy questions.
- Use query_academy_db for fees, durations, batch timings, start dates and seats.
- Answer in 2-3 short sentences of plain text. No markdown, no lists:
  your reply may be read aloud.
- If you don't know, say so and suggest contacting the front desk."""

agent = create_agent(
    llm,
    tools=[search_academy_docs, query_academy_db],
    system_prompt=SYSTEM_PROMPT,
    checkpointer=InMemorySaver(),   # conversation memory per session
)


def ask_agent(text: str, session_id: str) -> str:
    result = agent.invoke(
        {"messages": [{"role": "user", "content": text}]},
        config={"configurable": {"thread_id": session_id}},
    )
    return result["messages"][-1].content