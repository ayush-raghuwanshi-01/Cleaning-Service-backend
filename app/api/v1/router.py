from fastapi import APIRouter

from app.api.v1.endpoints import auth, business, orders

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(business.public_router)
api_router.include_router(business.customer_router)
api_router.include_router(business.admin_router)
api_router.include_router(orders.public_router)
api_router.include_router(orders.customer_router)
api_router.include_router(orders.admin_router)