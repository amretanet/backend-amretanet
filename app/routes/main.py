from fastapi import APIRouter
from app.routes.v1 import (
    auth_routes,
    ticket_routes,
    whatsapp_message_routes,
    coverage_area_routes,
    configuration_routes,
    customer_routes,
    option_routes,
    package_routes,
    odc_routes,
    odp_routes,
    router_routes,
    util_routes,
    information_routes,
    user_routes,
    invoice_routes,
)

router = APIRouter()
router.include_router(auth_routes.router)
router.include_router(invoice_routes.router)
router.include_router(ticket_routes.router)
router.include_router(whatsapp_message_routes.router)
router.include_router(coverage_area_routes.router)
router.include_router(customer_routes.router)
router.include_router(configuration_routes.router)
router.include_router(option_routes.router)
router.include_router(package_routes.router)
router.include_router(odc_routes.router)
router.include_router(odp_routes.router)
router.include_router(router_routes.router)
router.include_router(util_routes.router)
router.include_router(information_routes.router)
router.include_router(user_routes.router)
