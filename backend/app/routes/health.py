from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.database.db import get_db
from app.models.user import User
from app.utils.security import get_current_user

router = APIRouter(prefix="/health", tags=["Health"])

REQUIRED_TABLES = ("strategy_stats", "platform_metrics")


def _require_admin(user: User = Depends(get_current_user)):
    from fastapi import HTTPException
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def _get_expected_head() -> str | None:
    try:
        config = Config("alembic.ini")
        script = ScriptDirectory.from_config(config)
        heads = script.get_heads()
        if not heads:
            return None
        return heads[0] if len(heads) == 1 else ",".join(sorted(heads))
    except Exception:
        return None


@router.get("/db")
def db_health(db: Session = Depends(get_db), admin: User = Depends(_require_admin)):
    expected_head = _get_expected_head()
    result = {
        "status": "ok",
        "alembic_version": None,
        "expected_head": expected_head,
        "migration_in_sync": False,
        "tables": {},
    }

    try:
        version = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
        result["alembic_version"] = version
        if expected_head:
            expected_heads = {part.strip() for part in expected_head.split(",") if part.strip()}
            result["migration_in_sync"] = bool(version in expected_heads)

        for table_name in REQUIRED_TABLES:
            exists = db.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                        AND table_name = :table_name
                    )
                    """
                ),
                {"table_name": table_name},
            ).scalar()
            result["tables"][table_name] = bool(exists)

        open_trades = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM trades
                WHERE status IN ('OPEN', 'CLOSING')
                """
            )
        ).scalar()
        result["active_trades"] = int(open_trades or 0)

        if (not result["migration_in_sync"]) or (not all(result["tables"].values())):
            result["status"] = "degraded"
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)

    if result["status"] == "ok":
        return result
    if result["status"] == "degraded":
        return JSONResponse(content=result, status_code=503)
    return JSONResponse(content=result, status_code=500)
