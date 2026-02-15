from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from routers.dashboard_router import router as dashboard_router




from routers.dss_router import router as dss_router
from routers.upload_router import router as upload_router
# from routers.model_pred import router as model_pred
from routers.Search_router import router as Search
from routers.atlas_router import router as atlas_router

app = FastAPI()

# ✅ Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ✅ Register routers
app.include_router(dashboard_router)
app.include_router(dss_router)
app.include_router(upload_router)
# app.include_router(model_pred)
app.include_router(Search)
app.include_router(atlas_router)

# ✅ Graceful shutdown handler (prevents noisy CancelledError logs)
@app.on_event("shutdown")
async def shutdown_event():
    try:
        # Example: close DB connections, flush cache, etc.
        await asyncio.sleep(0)
    except asyncio.CancelledError:
        # Suppress cancellation errors during shutdown
        pass
