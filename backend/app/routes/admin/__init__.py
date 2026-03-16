from fastapi import APIRouter
from .admin_users import router as users_router
from .admin_trades import router as trades_router
from .admin_strategies import router as strategies_router
from .admin_plans import router as plans_router
from .admin_system import router as system_router

router = APIRouter()

router.include_router(users_router, prefix="/users", tags=["Admin - Users"])
router.include_router(trades_router, prefix="/trades", tags=["Admin - Trades"])
router.include_router(strategies_router, prefix="/strategies", tags=["Admin - Strategies"])
router.include_router(plans_router, prefix="/plans", tags=["Admin - Plans"])
router.include_router(system_router, prefix="/system", tags=["Admin - System"])
