import logging
from app.database.db import SessionLocal
from app.models.position import Position

logger = logging.getLogger(__name__)

class PositionTracker:

    def save_position(self, trade_data):
        db = SessionLocal()
        try:
            position = Position(
                id=trade_data.get("id"),
                user_id=trade_data.get("user_id"),
                symbol=trade_data.get("symbol"),
                side=trade_data.get("side"),
                entry=trade_data.get("entry"),
                sl=trade_data.get("sl"),
                tp=trade_data.get("tp"),
                be_trigger=trade_data.get("be_trigger"),
                is_reversal=trade_data.get("is_reversal", False),
                be_moved=trade_data.get("be_moved", False),
                status=trade_data.get("status", "OPEN")
            )
            db.add(position)
            db.commit()
            logger.info(f"Saved new position {position.id} to tracking db.")
        except Exception as e:
            logger.error(f"Error saving position: {e}")
            db.rollback()
        finally:
            db.close()

    def update_position(self, position_id, data):
        db = SessionLocal()
        try:
            position = db.query(Position).filter(Position.id == position_id).first()
            if position:
                for key, value in data.items():
                    setattr(position, key, value)
                db.commit()
                logger.info(f"Updated position {position_id} successfully.")
        except Exception as e:
            logger.error(f"Error updating position: {e}")
            db.rollback()
        finally:
            db.close()

    def close_position(self, position_id):
        self.update_position(position_id, {"status": "CLOSED"})
        logger.info(f"Position {position_id} marked as CLOSED.")
