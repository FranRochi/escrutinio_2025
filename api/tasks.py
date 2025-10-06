# api/tasks.py
"""
Proxy para mantener compatibilidad: reexporta tasks que ahora viven en backend.tasks
"""

from backend.tasks import process_outbox_row, flush_outbox

__all__ = ["process_outbox_row", "flush_outbox"]
