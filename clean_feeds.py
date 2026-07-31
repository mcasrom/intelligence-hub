import sys; sys.path.insert(0, ".")
from src.db import get_conn
conn = get_conn()
conn.execute("DELETE FROM feed_health WHERE feed_name LIKE '%Die Zeit%' OR feed_name LIKE '%Reuter%'")
print("Deleted:", conn.total_changes, "ghost entries")
conn.commit()
conn.close()
