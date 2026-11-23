from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from db import get_connection, init_db
from datetime import date
import requests
import os

SERPAPI_KEY = os.getenv("SERPAPI_KEY")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Plane Ticket Tracker API", lifespan=lifespan)


class RouteCreate(BaseModel):
    origin: str = Field(..., min_length=3, max_length=3)
    destination: str = Field(..., min_length=3, max_length=3)
    outbound_date: date
    target_price: int = Field(..., gt=0)


@app.get("/health")
def health():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
        return {"status": "ok", "database": "connected", "version": "v2"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database error: {e}")


@app.post("/routes", status_code=201)
def create_route(route: RouteCreate):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO routes (origin, destination, outbound_date, target_price)
                VALUES (%s, %s, %s, %s)
                RETURNING id, origin, destination, outbound_date, target_price, created_at;
                """,
                (route.origin.upper(), route.destination.upper(), route.outbound_date, route.target_price),
            )
            created = cur.fetchone()
        conn.commit()
    return created


@app.get("/routes")
def list_routes():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, origin, destination, outbound_date, target_price, created_at FROM routes ORDER BY id;")
            return cur.fetchall()


@app.get("/routes/{route_id}/prices")
def get_route_prices(route_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, price, checked_at
                FROM price_history
                WHERE route_id = %s
                ORDER BY checked_at DESC
                LIMIT 20;
                """,
                (route_id,),
            )
            return cur.fetchall()

@app.post("/routes/{route_id}/check")
def check_route_price(route_id: int):
    if not SERPAPI_KEY:
        raise HTTPException(status_code=500, detail="SERPAPI_KEY is not configured")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, origin, destination, outbound_date, target_price FROM routes WHERE id = %s;",
                (route_id,),
            )
            route = cur.fetchone()
            if not route:
                raise HTTPException(status_code=404, detail="Route not found")

            params = {
                "engine": "google_flights",
                "departure_id": route["origin"],
                "arrival_id": route["destination"],
                "outbound_date": str(route["outbound_date"]),
                "type": "2",
                "currency": "HUF",
                "api_key": SERPAPI_KEY,
            }
            resp = requests.get("https://serpapi.com/search.json", params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()

            flights = data.get("best_flights") or data.get("other_flights") or []
            prices = [f["price"] for f in flights if "price" in f]
            if not prices:
                raise HTTPException(status_code=404, detail="No flights found for this date")

            lowest_price = min(prices)
            cur.execute(
                "INSERT INTO price_history (route_id, price) VALUES (%s, %s);",
                (route_id, lowest_price),
            )
            conn.commit()

    return {
        "route_id": route_id,
        "origin": route["origin"],
        "destination": route["destination"],
        "outbound_date": str(route["outbound_date"]),
        "price": lowest_price,
        "target_price": route["target_price"],
    }

@app.delete("/routes/{route_id}")
def delete_route(route_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM price_history WHERE route_id = %s;", (route_id,))
            cur.execute("DELETE FROM routes WHERE id = %s RETURNING id;", (route_id,))
            deleted = cur.fetchone()
            if not deleted:
                raise HTTPException(status_code=404, detail="Route not found")
            conn.commit()
    return {"deleted_id": route_id}
