import os
import requests
from datetime import datetime, timedelta
from fast_flights import FlightQuery, Passengers, create_query, get_flights
import time

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

ORIGIN = "BUD"
DESTINATION = "AHO"
MAX_PRICE_HUF = 30000
MIN_DAYS = 3
MAX_DAYS = 8

START_DATE = datetime(2026, 9, 1)
END_DATE = datetime(2026, 10, 31)
STEP_DAYS = 3

def send_telegram(text):
    if not TOKEN or not CHAT_ID:
        print("Hiányzik a TOKEN vagy CHAT_ID")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=15)
    except Exception as e:
        print("Telegram hiba:", e)

def search_roundtrip(depart_date, return_date):
    try:
        query = create_query(
            flights=[
                FlightQuery(date=depart_date.strftime("%Y-%m-%d"), from_airport=ORIGIN, to_airport=DESTINATION),
                FlightQuery(date=return_date.strftime("%Y-%m-%d"), from_airport=DESTINATION, to_airport=ORIGIN)
            ],
            trip="round-trip",
            seat="economy",
            passengers=Passengers(adults=1),
        )
        result = get_flights(query)
        if result and hasattr(result, "flights") and result.flights:
            cheapest = min((f for f in result.flights if getattr(f, "price", None)), key=lambda x: x.price, default=None)
            if cheapest:
                return cheapest.price, cheapest
    except Exception as e:
        print(f"Hiba {depart_date.date()} → {return_date.date()}: {e}")
    return None, None

def main():
    print(f"Keresés indul: {ORIGIN} → {DESTINATION}")
    found = []
    current = START_DATE
    while current <= END_DATE:
        for duration in range(MIN_DAYS, MAX_DAYS + 1):
            return_date = current + timedelta(days=duration)
            if return_date > END_DATE + timedelta(days=7):
                continue
            print(f"{current.date()} → {return_date.date()} ({duration} nap)...", end=" ")
            price, _ = search_roundtrip(current, return_date)
            if price is not None:
                price_huf = int(price * 400)
                print(f"{price} → kb. {price_huf} Ft")
                if price_huf <= MAX_PRICE_HUF:
                    msg = (
                        f"<b>Olcsó jegy!</b>\n\n"
                        f"BUD → AHO\n"
                        f"Oda: {current.strftime('%Y-%m-%d')}\n"
                        f"Vissza: {return_date.strftime('%Y-%m-%d')}\n"
                        f"Tartózkodás: {duration} nap\n"
                        f"<b>Ár: kb. {price_huf} Ft</b>"
                    )
                    send_telegram(msg)
                    found.append(price_huf)
            else:
                print("nincs adat")
            time.sleep(2)
        current += timedelta(days=STEP_DAYS)
    if not found:
        send_telegram(f"Ma nem találtam {MAX_PRICE_HUF} Ft alatti jegyet BUD–AHO-ra (2027 júl-aug).")

if __name__ == "__main__":
    main()
