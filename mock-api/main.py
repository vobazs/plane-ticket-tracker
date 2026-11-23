import random
from datetime import datetime, timezone
from fastapi import FastAPI, Query

app = FastAPI(title="Mock Airline API")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/price")
def get_price(
    origin: str = Query(..., min_length=3, max_length=3, description="IATA code, e.g. BUD"),
    destination: str = Query(..., min_length=3, max_length=3, description="IATA code, e.g. BCN"),
):
    # Random price between 15,000 and 50,000 HUF (rounded to nearest 500)
    price = random.randrange(15000, 50500, 500)
    return {
        "origin": origin.upper(),
        "destination": destination.upper(),
        "price": price,
        "currency": "HUF",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
