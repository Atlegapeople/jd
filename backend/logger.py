import logging
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import WebSocket
from database import LogEntry
import asyncio

class DatabaseWebSocketHandler(logging.Handler):
    def __init__(self, db: Session, websocket: WebSocket = None, job_id: int = None):
        super().__init__()
        self.db = db
        self.websocket = websocket
        self.job_id = job_id
        self.progress = 0

    def emit(self, record):
        try:
            # Save log to database
            log_entry = LogEntry(
                job_id=self.job_id,
                level=record.levelname,
                message=self.format(record),
                created_at=datetime.utcnow()
            )
            self.db.add(log_entry)
            self.db.commit()

            # Determine progress heuristically
            message_lower = record.message.lower()
            if "starting" in message_lower:
                self.progress = 0
            elif "converting" in message_lower:
                self.progress = 20
            elif "extracting" in message_lower:
                self.progress = 40
            elif "processing" in message_lower:
                self.progress = 60
            elif "calculating" in message_lower:
                self.progress = 80
            elif "completed" in message_lower:
                self.progress = 100

            # Send message over WebSocket
            if self.websocket:
                asyncio.create_task(self._safe_send({
                    "type": "log",
                    "level": record.levelname,
                    "message": record.message,
                    "progress": self.progress
                }))

        except Exception:
            self.handleError(record)

    async def _safe_send(self, message: dict):
        try:
            await self.websocket.send_json(message)
        except Exception as e:
            logging.warning(f"WebSocket send failed: {str(e)}")


def setup_logger(db: Session, websocket: WebSocket = None, job_id: int = None):
    logger = logging.getLogger(f"job_processor_{job_id}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    handler = DatabaseWebSocketHandler(db, websocket, job_id)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
