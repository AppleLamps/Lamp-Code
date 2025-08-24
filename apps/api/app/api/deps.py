# Re-export the canonical dependency from app.db.session to avoid duplication
from app.db.session import get_db  # noqa: F401

