from __future__ import annotations

import os

import uvicorn
from dotenv import load_dotenv


load_dotenv()


if __name__ == "__main__":
    uvicorn.run(
        "service.service:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8080")),
        reload=os.environ.get("ENVIRONMENT", "development").lower() == "development",
    )
