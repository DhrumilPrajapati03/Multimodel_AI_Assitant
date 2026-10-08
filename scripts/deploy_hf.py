"""Deploy the app to a Hugging Face Docker Space.

Usage (from the project folder, after `hf auth login` with a WRITE token):
    python scripts/deploy_hf.py                     # -> <your-username>/academy-assistant
    python scripts/deploy_hf.py --space me/my-space --private

Needs in .env (or the environment):
    GROQ_API_KEY      your Groq key
    HF_DATABASE_URL   a hosted Postgres URL (e.g. Neon) - the Space can't reach localhost

It creates the Space if needed, stores both values as Space secrets, and uploads every
file git tracks (so .env, .venv and chroma_db never leave your machine). Re-run it to redeploy.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

SPACE_HEADER = """---
title: Academy Assistant
emoji: 🎙️
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
short_description: Voice and chat helpdesk for the academy
---

"""


def tracked_files():
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return sorted(p for p in out.splitlines() if (ROOT / p).is_file())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--space", help="Space id, e.g. user/academy-assistant")
    ap.add_argument("--private", action="store_true", help="only you can open the Space")
    args = ap.parse_args()

    groq_key = os.getenv("GROQ_API_KEY")
    db_url = os.getenv("HF_DATABASE_URL")
    if not groq_key:
        sys.exit("GROQ_API_KEY is not set in .env")
    if not db_url or "localhost" in db_url or "127.0.0.1" in db_url:
        sys.exit("Set HF_DATABASE_URL in .env to a hosted Postgres URL (e.g. from neon.tech).")

    api = HfApi()
    user = api.whoami()["name"]
    space = args.space or f"{user}/academy-assistant"

    api.create_repo(space, repo_type="space", space_sdk="docker", private=args.private, exist_ok=True)
    api.add_space_secret(space, "GROQ_API_KEY", groq_key)
    api.add_space_secret(space, "DATABASE_URL", db_url)

    files = tracked_files()
    ops = [CommitOperationAdd(path_in_repo=p, path_or_fileobj=str(ROOT / p)) for p in files if p != "README.md"]
    readme = (ROOT / "README.md").read_text(encoding="utf-8") if (ROOT / "README.md").exists() else ""
    ops.append(CommitOperationAdd(path_in_repo="README.md", path_or_fileobj=(SPACE_HEADER + readme).encode()))

    # Remove files deleted locally since the last deploy.
    local = set(files) | {"README.md", ".gitattributes"}
    ops += [CommitOperationDelete(path_in_repo=p)
            for p in api.list_repo_files(space, repo_type="space") if p not in local]

    api.create_commit(space, repo_type="space", operations=ops, commit_message="Deploy from local repo")
    print(f"Uploaded {len(files)} files. Build logs: https://huggingface.co/spaces/{space}?logs=build")
    print(f"App URL (once built): https://{space.replace('/', '-').lower()}.hf.space")


if __name__ == "__main__":
    main()
