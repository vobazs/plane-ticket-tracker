import os
import requests
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


def fetch_lowest_price(origin: str, destination: str, outbound_date: str):
    if not SERPAPI_KEY:
        print("SERPAPI_KEY is not set.")
        return None

    params = {
        "engine": "google_flights",
        "departure_id": origin,
        "arrival_id": destination,
        "outbound_date": outbound_date,
        "type": "2",
        "currency": "HUF",
        "api_key": SERPAPI_KEY,
    }
    try:
        resp = requests.get("https://serpapi.com/search.json", params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        flights = data.get("best_flights") or data.get("other_flights") or []
        prices = [f["price"] for f in flights if "price" in f]
        return min(prices) if prices else None
    except Exception as e:
        print(f"Error fetching price for {origin}->{destination}: {e}")
        return None


def send_discord_alert(origin, destination, outbound_date, price, target_price):
    if not DISCORD_WEBHOOK_URL:
        return
    message = (
        f"✈️ **ÁRRIASZTÁS!** `{origin} -> {destination}` ({outbound_date})\n"
        f"Aktuális ár: **{price} HUF** (Célár: {target_price} HUF)"
    )
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=10)
        resp.raise_for_status()
        print("  -> Discord értesítés elküldve!")
    except Exception as e:
        print(f"  -> Hiba a Discord értesítés küldésekor: {e}")


def main():
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, origin, destination, outbound_date, target_price FROM routes;")
            routes = cur.fetchall()

            if not routes:
                print("No routes to check.")
                return

            for route in routes:
                date_str = route["outbound_date"].isoformat()
                price = fetch_lowest_price(route["origin"], route["destination"], date_str)
                if price is None:
                    print(f"[NO DATA] {route['origin']}->{route['destination']} on {date_str}")
                    continue

                print(f"[OK] {route['origin']}->{route['destination']} ({date_str}): {price} HUF")
                cur.execute(
                    "INSERT INTO price_history (route_id, price) VALUES (%s, %s);",
                    (route["id"], price),
                )

                if price <= route["target_price"]:
                    print(f"  -> [ALERT! Target price reached: {price} <= {route['target_price']}]")
                    send_discord_alert(
                        route["origin"],
                        route["destination"],
                        date_str,
                        price,
                        route["target_price"],
                    )
                conn.commit()


if __name__ == "__main__":
    main()
