import uvicorn
from fastapi import FastAPI, HTTPException, status
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config
from src.utils.logger import setup_logger
from scripts.refresh_cache import run_refresh
from scripts.refresh_record_cache import run_refresh_record

logger = setup_logger(__name__)

app = FastAPI(
    title="Billing Cache API",
    description="API to manage and trigger billing cache refreshes",
    version="1.0.0"
)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "billing-api"}

@app.post("/api/v1/cache/refresh")
async def trigger_cache_refresh():
    logger.info("Cache refresh triggered via API")
    
    # Run the refresh logic
    stats = run_refresh()
    
    if stats["status"] == "success":
        logger.info(f"API Cache refresh successful: {stats}")
        return {
            "message": "Cache refresh completed successfully",
            "details": stats
        }
    else:
        logger.error(f"API Cache refresh failed: {stats['message']}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cache refresh failed: {stats['message']}"
        )

@app.post("/api/v1/cache/refresh-record")
async def trigger_record_cache_refresh():
    logger.info("Recording cache refresh triggered via API")
    
    stats = run_refresh_record()
    
    if stats["status"] == "success":
        logger.info(f"API Recording Cache refresh successful: {stats}")
        return {
            "message": "Recording cache refresh completed successfully",
            "details": stats
        }
    else:
        logger.error(f"API Recording Cache refresh failed: {stats['message']}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Recording cache refresh failed: {stats['message']}"
        )

def main():
    logger.info("Starting Billing API Server...")
    uvicorn.run(app, host="0.0.0.0", port=8005)

if __name__ == "__main__":
    main()
