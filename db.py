import os
from supabase import Client, create_client

URL: str = os.environ.get("SUPABASE_URL")
KEY: str = os.environ.get("SUPABASE_KEY")

SUPABASE: Client = create_client(URL, KEY)
