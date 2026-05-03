from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from supabase import Client, create_client


load_dotenv()


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.environ.get("SUPABASE_ANON_KEY", "").strip()
    )
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_ANON_KEY or SUPABASE_SERVICE_ROLE_KEY are required")
    return create_client(url, key)

