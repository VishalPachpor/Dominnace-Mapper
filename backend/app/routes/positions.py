from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.utils.security import get_current_user
from app.models.position import Position
from app.database.db import get_db
from app.services.metaapi_service import get_open_positions, close_position
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("")
async def get_positions(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Returns live open positions from the broker (MetaApi).
    Falls back to DB positions if MetaApi is not configured.
    """
    meta_account_id = getattr(user, "meta_account_id", None)

    if meta_account_id:
        try:
            broker_positions = await get_open_positions(meta_account_id)
            return [
                {
                    "id": p.get("id", ""),
                    "symbol": p.get("symbol", ""),
                    "side": p.get("type", ""),
                    "type": p.get("type", ""),
                    "volume": p.get("volume", 0),
                    "entry_price": p.get("openPrice", 0),
                    "entry": p.get("openPrice", 0),
                    "current_price": p.get("currentPrice", 0),
                    "currentPrice": p.get("currentPrice", 0),
                    "pnl": p.get("profit", 0),
                    "profit": p.get("profit", 0),
                    "sl": p.get("stopLoss", 0),
                    "tp": p.get("takeProfit", 0),
                }
                for p in broker_positions
            ]
        except Exception as e:
            logger.error(f"Failed to fetch live positions for user {user.id}: {e}")

    # Fallback: DB positions
    positions = db.query(Position).filter(
        Position.user_id == user.id,
        Position.status == "OPEN"
    ).all()
    return positions


@router.post("/close-all")
async def close_all_positions(user=Depends(get_current_user)):
    """Close all open positions for the current user."""
    meta_account_id = getattr(user, "meta_account_id", None)
    if not meta_account_id:
        raise HTTPException(status_code=400, detail="No MetaApi account connected")

    try:
        broker_positions = await get_open_positions(meta_account_id)
        closed = 0
        errors = []

        for p in broker_positions:
            pid = p.get("id", "")
            try:
                await close_position(meta_account_id, pid)
                closed += 1
            except Exception as e:
                errors.append({"position_id": pid, "error": str(e)})
                logger.error(f"Failed to close position {pid}: {e}")

        logger.info(f"User {user.id} closed {closed}/{len(broker_positions)} positions")
        return {"status": "done", "closed": closed, "total": len(broker_positions), "errors": errors}
    except Exception as e:
        logger.error(f"Failed to close all positions for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to close positions: {str(e)}")


@router.post("/{position_id}/close")
async def close_single_position(position_id: str, user=Depends(get_current_user)):
    """Close a specific position by its broker position ID."""
    meta_account_id = getattr(user, "meta_account_id", None)
    if not meta_account_id:
        raise HTTPException(status_code=400, detail="No MetaApi account connected")

    try:
        result = await close_position(meta_account_id, position_id)
        logger.info(f"User {user.id} closed position {position_id}")
        return {"status": "closed", "result": result}
    except Exception as e:
        logger.error(f"Failed to close position {position_id} for user {user.id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to close position: {str(e)}")
