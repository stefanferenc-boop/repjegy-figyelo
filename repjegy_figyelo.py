import os
import requests
from datetime import datetime, timedelta
import time
import re
from playwright.sync_api import sync_playwright

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

ORIGIN = "BUD"
DESTINATION = "BRI"
MAX_PRICE_HUF = 50000
MIN_DAYS = 1
MAX_DAYS = 2

START_DATE = datetime(2026, 10, 10)
END_DATE = datetime(2026, 10, 15)
STEP_DAYS = 1

def send_telegram(text):
    if not TOKEN or not CHAT_ID:
        print("Hiányzik a TOKEN vagy CHAT_ID")
        return
    url = f"https://telegram.org{TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print("\nTelegram hiba:", e)

def scrape_google_flights(page, depart_str, return_str):
    """Lekérdezi a Google Flights oldalt az adott dátumokra"""
    url = f"https://google.com{DESTINATION}%20from%20{ORIGIN}%20on%20{depart_str}%20through%20{return_str}"
    
    try:
        page.goto(url, wait_until="commit", timeout=30000)
        
        # 1. Süti (Cookie) ablak kezelése, ha megjelenik
        try:
            # Megvárjuk, hátha felugrik a Google hozzájárulási nyilatkozat
            accept_button = page.locator('button:has-text("Accept all"), button:has-text("Elf उत्पाद"), button:has-text("Mind elfogadása")')
            if accept_button.is_visible(timeout=3000):
                accept_button.click()
                page.wait_for_load_state("networkidle")
        except:
            pass # Ha nincs süti ablak, megyünk tovább

        # 2. Megvárjuk, amíg az árakat tartalmazó listaelemek betöltődnek
        # A Google Flights-on a főbb találati elemek szerepköre általában 'listitem'
        page.wait_for_selector('li', timeout=8000)
        
        # 3. Kinyerjük az oldalon található összes szöveget, ami árakra utalhat
        content = page.content()
        
        # Reguláris kifejezéssel keresünk "X Ft" vagy "X HUF" formátumot
        # A Google Actions környezetben gyakran magyarul vagy angolul renderel
        prices = []
        
        # Minták HUF/Ft vagy EUR/€ árak kiszűrésére
        huf_matches = re.findall(r'([\d\s ]+)\s*(?:Ft|HUF)', content)
        for match in huf_matches:
            clean_price = int(re.sub(r'[\s ]', '', match))
            if clean_price > 1000: # Kiszűrjük a túl kicsi zajokat (pl. 1 nap stb.)
                prices.append(clean_price)
                
        if not prices:
            # Megpróbáljuk az EUR formátumot is, ha a Google átváltana
            eur_matches = re.findall(r'(?:€|EUR)\s*([\d\s ]+)', content)
            for match in eur_matches:
                clean_price = int(re.sub(r'[\s ]', '', match)) * 400
                prices.append(clean_price)

        if prices:
            cheapest = min(prices)
            return cheapest
            
    except Exception as e:
        # Ha időtúllépés van vagy nem talál elemet, finoman hibára futunk a logban
        print(f"[Hiba: {str(e)[:40]}]", end=" ")
        
    return None

def main():
    print(f"Lopakodó Google Flights keresés indul: {ORIGIN} → {DESTINATION}")
    found = []
    
    with sync_playwright() as p:
        # Böngésző indítása fejlett álcázási paraméterekkel
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled', # Eltünteti a robot flaget
                '--lang=hu-HU,hu' # Magyar nyelvi környezet szimulálása
            ]
        )
        
        # Kontextus létrehozása egyedi User-Agent-tel
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            viewport={'width': 1280, 'height': 800},
            locale='hu-HU'
        )
        
        page = context.new_page()
        
        current = START_DATE
        while current <= END_DATE:
            for duration in range(MIN_DAYS, MAX_DAYS + 1):
                return_date = current + timedelta(days=duration)
                if return_date > END_DATE + timedelta(days=7):
                    continue
                
                dep_str = current.strftime("%Y-%m-%d")
                ret_str = return_date.strftime("%Y-%m-%d")
                
                print(f"{dep_str} → {ret_str} ({duration} nap)...", end=" ")
                
                price_huf = scrape_google_flights(page, dep_str, ret_str)
                
                if price_huf is not None:
                    print(f"Talált ár: {price_huf} Ft")
                    if price_huf <= MAX_PRICE_HUF:
                        msg = (
                            f"<b>Olcsó jegy (Google Flights)!</b>\n\n"
                            f"{ORIGIN} → {DESTINATION}\n"
                            f"Oda: {dep_str}\n"
                            f"Vissza: {ret_str}\n"
                            f"Tartózkodás: {duration} nap\n"
                            f"<b>Ár: kb. {price_huf} Ft</b>"
                        )
                        send_telegram(msg)
                        found.append(price_huf)
                else:
                    print("nincs adat")
                
                time.sleep(4) # Megfelelő szünet az IP-tiltás ellen
            current += timedelta(days=STEP_DAYS)
            
        browser.close()
        
    if not found:
        send_telegram(f"Nem találtam {MAX_PRICE_HUF} Ft alatti jegyet {ORIGIN}–{DESTINATION}-ra {START_DATE.strftime('%Y-%m-%d')} - {END_DATE.strftime('%Y-%m-%d')} között.")

if __name__ == "__main__":
    main()
