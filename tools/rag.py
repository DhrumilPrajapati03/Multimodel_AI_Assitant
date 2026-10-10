from langchain_core.tools import tool

from tools.docstore import search


@tool
def search_academy_docs(query: str) -> str:
    """Search the academy documents: syllabus, policies, FAQs, handbook and any notices
    the staff uploaded. Use this for course content, topics covered, rules and general academy info."""
    hits = search(query, k=4)
    if not hits:
        return "Nothing relevant found in the documents."
    return "\n\n".join(f"[{h['name']}, page {h['page']}]\n{h['content']}" for h in hits)
