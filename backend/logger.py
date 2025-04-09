import logging
from datetime import datetime
from typing import Optional, Dict
from models import LogEntry
from database import db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def log_to_db(level: str, message: str, metadata: Optional[Dict] = None):
    """Log message to both console and database."""
    try:
        # Log to console
        if level == 'INFO':
            logger.info(message)
        elif level == 'WARNING':
            logger.warning(message)
        elif level == 'ERROR':
            logger.error(message)
        elif level == 'DEBUG':
            logger.debug(message)
        
        # Create log entry
        log_entry = LogEntry(
            level=level,
            message=message,
            metadata=metadata
        )
        
        # Save to database
        await db.logs.insert_one(log_entry.dict(by_alias=True))
        
    except Exception as e:
        logger.error(f"Error logging to database: {str(e)}")
