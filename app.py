import os
import re
import json
import math
import uuid
import logging
import tempfile
import requests
import pandas as pd
from functools import lru_cache
from flask import Flask, render_template, request, session, url_for, redirect, jsonify
from dotenv import load_dotenv
from groq import Groq
from collections import defaultdict
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

# ================================================================
# 1. LOAD CSV FILES
# ================================================================

cities_df    = pd.read_csv("data/city.csv")
suppliers_df = pd.read_csv("data/supplier.csv")
categories_df= pd.read_csv("data/service_category.csv")

try:
    services_df = pd.read_csv("data/supplier_service.csv")
    logger.info(f"Loaded {len(services_df)} supplier services")
except FileNotFoundError:
    logger.warning("supplier_service.csv not found. Creating empty DataFrame.")
    services_df = pd.DataFrame(columns=[
        "supplier_service_id","supplier_id","service_category_id",
        "supplier_service_name","is_active","deleted"
    ])

for _df in [cities_df, suppliers_df, services_df, categories_df]:
    for _col in _df.columns:
        if _df[_col].dtype == object:
            _df[_col] = _df[_col].astype(str).str.strip()

# ================================================================
# LOOKUP MAPS
# ================================================================

MEAL_PLAN_MAP = {
    "1":"Room Only","2":"Bed & Breakfast","3":"Half Board",
    "4":"Full Board","7":"All Inclusive","9":"Room Only","10":"Full Board",
}

ROOM_CATEGORY_MAP = {
    "1":"Standard","2":"Deluxe","6":"Superior","7":"Executive",
    "8":"Executive Suite","9":"Deluxe Suite","10":"Luxury Suite",
    "11":"Colonial Room","12":"Ocean View Room","13":"Direct Ocean View",
    "15":"Superior Spa Rooms","16":"Deluxe Ocean Front","17":"Deluxe Premier",
    "18":"Lux Room","19":"Dream Room","20":"Dream Ocean Room","21":"Ozo Suite",
    "22":"Suite","23":"Superior Suites","24":"Kingfisher Lodge","25":"Eagle Lodge",
    "26":"Penthouse","27":"Family Suite","28":"Junior Suite","29":"Standard New Wing",
    "31":"Garden Suite","32":"Master Suite","33":"Super Deluxe","34":"Paradise Room",
    "35":"Paradise Suite","36":"Jungle Chalet","37":"Beach Chalet","39":"Bungalow",
    "40":"Superior Suite","41":"Paddy Room","43":"Panoramic","44":"Sea View Suite",
    "45":"Garden Room","46":"Ocean Suite","47":"Sea View Upper","48":"Sea View Ground",
    "49":"Luxury Panoramic","51":"Sea View Room","52":"Royal Suite","53":"Chalet",
    "54":"Garden Suite","56":"Water Room","57":"Forest Room","58":"Wallawwa Bedroom",
    "59":"White Room","60":"Master Room","61":"Bawa Room","62":"Family Room",
    "63":"Honeymoon Suite","64":"Standard Non-AC","65":"Superior Sea View",
    "66":"Deluxe Sea View","67":"Landmark","68":"Landmark Sea View","72":"Studio",
    "73":"Studio Sea View","74":"Junior Suite Sea View","76":"1 Bed Suite",
    "77":"2 Bed Suite","78":"Cottage","79":"Nutcracker Suite","81":"Superior Category",
    "82":"Club Suite","83":"Silk Room","84":"Duplex Cottage","85":"Superior Cottage",
    "86":"Deluxe Duplex Cottage","87":"Deer Park Cottage","88":"Super Deluxe Suite",
    "89":"Rose Petal Suite","90":"Infinite Suite","91":"Whole Villa",
    "92":"Sea Escape Deluxe","93":"Aqua Romance","94":"Ocean Privilege Suite",
    "95":"Aqua Marina","96":"Grande Reviera","97":"Mansion Suite",
    "101":"Corner Suite","102":"Middle Suite","103":"Premier Garden View",
    "104":"Premier Ocean View","105":"Garden Pool Villa","106":"Ocean View Pool Villa",
    "107":"Beach Pool Villa","108":"Two Bedroom Pool Villa","109":"Deluxe Ocean View",
    "111":"Presidential Suite","112":"Damunu Suite","122":"Deluxe Suite with Pool",
    "123":"Mountain View Room","124":"Garden View Room","125":"Superior Eco Lodge",
    "126":"Mudhouse","127":"Dormitory","134":"Deluxe Bungalow",
    "135":"Superior Ocean View","137":"Executive Ocean View","139":"Ocean View Suite",
    "140":"Superior Bungalow","141":"Tower Suite","142":"Guest Hut",
    "143":"Comfort Room","144":"En Suite Tent","145":"Superior City View",
    "147":"Ulagalla Villa","148":"Standard Bungalow","149":"Park Suite",
    "150":"Residence Suite","151":"Superior Deluxe","152":"Premium",
    "153":"Superior Deluxe Suite","154":"Wooden Cabana Non-AC","155":"Superior Cabana",
    "156":"Cabin Room","157":"Marsh Room No Pool","158":"Paddy Marsh With Pool",
    "162":"Club Lodge","163":"Deluxe Villa","164":"Garden Villa",
    "165":"Family Bungalow","166":"Premium Deluxe","167":"Deluxe Family Residence",
    "168":"Premium Deluxe Spa Suite","169":"Deluxe City View","170":"Beach Studio",
    "171":"Waterfront Chalet","172":"Superior Sea View","173":"Ocean Studio",
    "180":"Loft","183":"Pool Chalet","186":"Garden Deluxe","187":"Theme Suite",
    "188":"Lagoon Cabana","192":"Balcony Room","194":"Beach Cabana",
    "197":"Wooden Cabana","199":"Camping Tent","200":"Classic",
    "201":"Deluxe Delight","209":"Tree House","210":"Semi-Luxury Tent",
    "213":"Grand Apartment","222":"Garden Chalet","226":"Amangalla Suite",
    "228":"Luxury Tented Suite","244":"Full Villa","248":"Superior Pool Terrace",
    "249":"Villa Sea View","251":"Beach Villa","252":"Bay Suite",
    "254":"Chalet Villa","255":"Superior Chalet","256":"Deluxe Chalet",
    "257":"Luxury Tent","263":"Superior Family Room","267":"Deluxe Tent",
    "270":"Villa with Jacuzzi","271":"Villa with Plunge Pool",
    "272":"Deluxe Poolside Terrace","273":"Family Residence","274":"Honeymoon Deluxe",
    "276":"Jacuzzi Suite","277":"Plunge Pool Suite","282":"Tent",
    "285":"Superior Mountain View","293":"2-Bedroom Villa",
    "294":"Luxury Garden Chalet","295":"Courtyard Suite","296":"Premium Suite",
    "297":"Apartment Suite","305":"Bedroom","306":"Cabana","307":"Villa",
    "311":"Superior Lodge","334":"Palm Suite","335":"Beach Leisure Suite",
    "336":"Beach Balcony Suite","337":"Beach Access Terrace Suite",
    "338":"Lounge Pool Master Suite","346":"Large Sea View","348":"Beach Suite",
    "349":"Family Villa","350":"Beach Suite with Pool","355":"1 Bedroom Apartment",
    "356":"2 Bedroom Apartment","359":"Beach Side","360":"Land Side",
    "361":"Luxury AC Room","362":"Standard Suite","363":"Deluxe Sea View Balcony",
    "366":"Ulagalla Chalet with Pool","387":"Suite","400":"Premier",
    "401":"Deluxe Garden","408":"Comfort Tent","417":"Premier Residence",
    "418":"Grand Residence","446":"Lake View Suite","447":"Premier Golf Suite",
    "448":"Premier Ocean Suite","453":"Solo Suite","454":"Deluxe Lagoon View",
    "455":"Deluxe Pool Side","456":"One Bedroom Ocean View Suite",
    "458":"One Bedroom Garden Pool Villa","459":"Presidential Pool Suite",
    "466":"Bawa Suite","469":"King Villa","470":"Queen Villa","471":"Gem Suite",
    "477":"Luxury Tent","478":"Club Room","479":"Dwelling without Plunge Pool",
    "480":"Dwelling with Plunge Pool","481":"Randholee Suite","482":"Plantation Suite",
    "485":"Boutique Luxury","486":"King Suite Ocean View","487":"Suite Garden View",
    "488":"Deluxe Family Suite","489":"Deluxe Terrace Ocean View",
    "490":"Grand Deluxe Ocean View","491":"One Bedroom Suite",
    "498":"Suite with Plunge Pool","499":"Bay View Pool Suite",
    "501":"Mountain View Chalet","505":"Deluxe Villa",
    "507":"Duplex Villa with Plunge Pool","509":"Kandyan Suite",
    "511":"Premium Family Villa with Pool","529":"Heritage Suite",
    "530":"Grand Suite","531":"Tower Room",
}

CURRENCY_MAP = {
    "0":"LKR","1":"USD","2":"USD","3":"EUR","5":"GBP","8":"AUD","9":"LKR",
}
RATE_TYPE_MAP = {"1":"Fixed Rate","2":"Per Person","3":"Per Vehicle"}
RIDE_TYPE_MAP = {"0":"Standard","1":"Jeep","2":"Boat","3":"Boat","4":"Train"}
VEHICLE_CATEGORY_MAP = {
    "1":"Car","3":"Van","4":"Micro Van","5":"33-Seater Coach",
    "6":"Large Coach","7":"Baggage Van","8":"Mini Coach",
    "9":"KDH High Roof Van","10":"SUV",
}

meal_plan_dict        = MEAL_PLAN_MAP
room_category_dict    = ROOM_CATEGORY_MAP
currency_dict         = CURRENCY_MAP
ride_type_dict        = RIDE_TYPE_MAP
vehicle_category_dict = VEHICLE_CATEGORY_MAP
vehicle_dict          = {}


def _resolve(val, mapping):
    if val is None:
        return ""
    s = str(val).strip()
    if s.lower() in ("nan","none","null",""):
        return ""
    try:
        s = str(int(float(s)))
    except (ValueError, TypeError):
        return s
    return mapping.get(s, "")


# ================================================================
# 2. JOIN TABLES
# ================================================================

_sup_city = suppliers_df.merge(cities_df,     on="city_id",             how="left")
_svc_sup  = services_df.merge(_sup_city,       on="supplier_id",         how="left")
full_df   = _svc_sup.merge(categories_df,      on="service_category_id", how="left")

if "is_active" in full_df.columns:
    full_df = full_df[full_df["is_active"].astype(str) == "1"].copy()

for _col in full_df.columns:
    if full_df[_col].dtype == object:
        full_df[_col] = full_df[_col].astype(str).str.strip()

# ================================================================
# 3. INDEXES
# ================================================================

city_index = {
    str(row["city_name"]).lower(): row.to_dict()
    for _, row in cities_df.iterrows()
}
all_city_names = sorted(
    cities_df["city_name"].dropna().str.strip().str.title().unique().tolist()
)

def norm_city(city):
    return str(city).strip().lower()

# ================================================================
# 4. DISTANCE
# ================================================================

def haversine(c1, c2):
    R = 6371
    la1,lo1 = map(math.radians, c1)
    la2,lo2 = map(math.radians, c2)
    d = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return R * 2 * math.atan2(math.sqrt(d), math.sqrt(1-d))

# ================================================================
# 5. ROUTE
# ================================================================

_COLOMBO = (6.9271, 79.8612)

def sort_places_by_distance(places):
    known, unknown = {}, []
    for p in places:
        row = city_index.get(norm_city(p))
        if row is not None:
            known[p] = (float(row["latitude"]), float(row["longitude"]))
        else:
            unknown.append(p)
    if not known:
        return places
    start = next((k for k in known if norm_city(k) == "colombo"), None)
    if not start:
        start = min(known, key=lambda x: haversine(_COLOMBO, known[x]))
    route, remaining, cur = [start], [p for p in known if p != start], start
    while remaining:
        nxt = min(remaining, key=lambda x: haversine(known[cur], known[x]))
        route.append(nxt); remaining.remove(nxt); cur = nxt
    return route + unknown

# ================================================================
# 6. GROQ — EXTRACT TRIP INFO
# ================================================================

def extract_trip_info_groq(email_text):
    city_sample = ", ".join(all_city_names[:80])
    prompt = f"""
Read the travel enquiry email and return ONLY a valid JSON object — no markdown, no explanation.

Required JSON:
{{
  "days"         : <integer, default 7>,
  "budget"       : <integer total USD or null if not mentioned>,
  "adults"       : <integer, default 1>,
  "children"     : <integer, default 0>,
  "travel_style" : <string, e.g. "Cultural", "Adventure", "Beach", "Wildlife">,
  "meal_plan"    : <string — extract or "Breakfast and Dinner">,
  "places"       : <list of Sri Lanka city name strings>
}}

Rules for "places":
- If the email lists destinations explicitly → use exactly those names.
- If NO destinations are mentioned → choose the best cities from this list
  based on days, budget and travel style: {city_sample}
- Always prefer city names from the list above.

Rules for "budget":
- Extract the total trip budget if mentioned. If not → return null.

Email:
\"\"\"
{email_text}
\"\"\"
"""
    try:
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role":"system","content":"You extract structured travel data from emails. Output only valid JSON, nothing else."},
                {"role":"user",  "content":prompt},
            ],
            temperature=0.0, max_tokens=512,
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"```(?:json)?","",raw).strip().strip("`")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from Groq: {raw}")
            return _extract_regex(email_text)
        days         = int(data.get("days",7))
        budget       = int(data["budget"]) if data.get("budget") else None
        adults       = int(data.get("adults",1))
        children     = int(data.get("children",0))
        travel_style = str(data.get("travel_style","General Sightseeing")).strip()
        meal_plan    = str(data.get("meal_plan","Breakfast and Dinner")).strip()
        places       = [str(p).strip().title() for p in data.get("places",[]) if str(p).strip()]
        return days, budget, adults, children, places, travel_style, meal_plan
    except Exception as e:
        logger.warning(f"Groq extraction failed ({e}), using regex fallback.")
        return _extract_regex(email_text)

def _extract_regex(email):
    dm = re.search(r"(\d+)\s*day",        email.lower())
    bm = re.search(r"(usd|\$)\s*([\d,]+)",email.lower())
    am = re.search(r"(\d+)\s*adult",      email.lower())
    cm = re.search(r"(\d+)\s*child",      email.lower())
    sm = re.search(r"travel style[:\s]+([^\n\r.]+)",email,re.IGNORECASE)
    mm = re.search(r"meal[s]?[:\s]+([^\n\r.]+)",    email,re.IGNORECASE)
    days         = int(dm.group(1))              if dm else 7
    budget       = int(bm.group(2).replace(",","")) if bm else None
    adults       = int(am.group(1))              if am else 1
    children     = int(cm.group(1))              if cm else 0
    travel_style = sm.group(1).strip()           if sm else "General Sightseeing"
    meal_plan    = mm.group(1).strip()           if mm else "Breakfast and Dinner"
    pref = re.search(
        r"preferred destinations[:\s]*(.*?)(travel style|budget range|we are interested|$)",
        email, re.DOTALL|re.IGNORECASE
    )
    places = []
    if pref:
        for p in re.split(r"[,\n]",pref.group(1)):
            clean = p.strip(" .\n*•-")
            if len(clean) > 2:
                places.append(clean.title())
    if not places:
        defaults = ["Colombo","Kandy","Nuwara Eliya","Ella","Yala","Bentota"]
        places = [p for p in defaults if p.lower() in city_index]
    return days, budget, adults, children, places, travel_style, meal_plan

# ================================================================
# BUDGET TIER
# ================================================================

def get_budget_tier(budget, days, adults, children):
    total_pax = max(1, adults + (children * 0.5))
    ppd = budget / (days * total_pax) if budget and days and total_pax else None
    if ppd is None or 80 <= ppd <= 200:
        return {"tier":"medium","label":"Medium Budget (~USD 80–200 per person/day)",
                "hotel_quality":"3-star or boutique hotels, comfortable rooms with breakfast included",
                "meal_quality":"local restaurants and hotel dining, mix of Sri Lankan and international cuisine",
                "per_person_per_day":ppd}
    elif ppd < 80:
        return {"tier":"budget","label":f"Budget (~USD {ppd:.0f} per person/day)",
                "hotel_quality":"guesthouses, budget hotels or homestays",
                "meal_quality":"local warungs, street food and budget restaurants",
                "per_person_per_day":ppd}
    else:
        return {"tier":"luxury","label":f"Luxury (~USD {ppd:.0f} per person/day)",
                "hotel_quality":"5-star resorts and luxury villas with full board or half board",
                "meal_quality":"fine dining, resort restaurants and private chef experiences",
                "per_person_per_day":ppd}

# ================================================================
# 7. SCHEDULE BUILDER
# ================================================================

def build_schedule(days, places):
    if not places:
        return [["Colombo"]] * days
    places = sort_places_by_distance(places)
    n = len(places)
    if days == n:
        return [[city] for city in places]
    if days > n:
        base, rem = divmod(days, n)
        schedule = []
        for i, city in enumerate(places):
            nights = base + (1 if i < rem else 0)
            schedule.extend([[city]] * nights)
        return schedule[:days]
    if days == 1:
        return [places]
    base, extra = divmod(n, days)
    schedule, idx = [], 0
    for day in range(days):
        count = base + (1 if day < extra else 0)
        schedule.append(places[idx:idx+count])
        idx += count
    return schedule

# ================================================================
# 8. CITY SERVICES
# ================================================================

GUEST_CATEGORIES = {
    "Transport","Accommodation","Entrance Fees","Meals",
    "Ride Types","Driver / Vehicle & Guides","Transfers",
    "Flight \\ Ferry \\ Train","Shopping Outlets","Additional Expenses",
}

RATING_MAP = {
    "1":"5★","2":"4★","3":"3★","4":"2★",
    "6":"Boutique","7":"Guesthouse","8":"Luxury Villa",
    "9":"Eco / Nature","10":"Guesthouse","11":"Homestay",
    "12":"Apartment","13":"Ultra Luxury","14":"Boutique Villa",
}

TIER_RATING_PREFERENCE = {
    "luxury":[13,1,14,8,2],
    "medium":[2,3,8,9,6],
    "budget":[6,3,7,10,11,4],
}

def get_city_services(city):
    df = full_df[full_df["city_name"].str.lower() == norm_city(city)]
    result = {}
    for row in df.itertuples():
        cat = getattr(row,"service_category_name","").strip()
        srv = getattr(row,"supplier_service_name","").strip()
        sup = getattr(row,"supplier_name","").strip()
        if cat not in GUEST_CATEGORIES:
            continue
        result.setdefault(cat,{"suppliers":[],"services":[]})
        if sup and sup != "nan" and sup not in result[cat]["suppliers"]:
            result[cat]["suppliers"].append(sup)
        if srv and srv != "nan" and srv not in result[cat]["services"]:
            result[cat]["services"].append(srv)
    return result

def get_city_description(city):
    row = city_index.get(norm_city(city))
    if row is None:
        return ""
    desc = str(row.get("city_description","")).strip()
    if desc in ("nan","None","NULL",""):
        return ""
    return desc.replace("''","'").replace("\\n"," ").replace("\n"," ").strip()

# ================================================================
# 8b. HOTELS BY TIER
# ================================================================

def get_city_hotels_by_tier(city, tier="medium", max_hotels=1, exclude_hotels=None):
    if exclude_hotels is None:
        exclude_hotels = set()
    preferred = TIER_RATING_PREFERENCE.get(tier, TIER_RATING_PREFERENCE["medium"])

    mask_city = full_df["city_name"].str.lower() == norm_city(city)
    mask_acc  = full_df["service_category_name"] == "Accommodation"
    df_hotels = full_df[mask_city & mask_acc][
        ["supplier_id","supplier_name","supplier_rating_id",
         "supplier_website","supplier_image","supplier_image1"]
    ].drop_duplicates("supplier_id").copy()

    acc_cat_row = categories_df[
        categories_df["service_category_name"].str.lower() == "accommodation"
    ]
    acc_cat_id = str(acc_cat_row.iloc[0]["service_category_id"]) \
        if not acc_cat_row.empty else "2"

    hotels = []
    for row in df_hotels.itertuples():
        name = str(row.supplier_name).strip()
        if not name or name in ("nan","None","NULL","") or name in exclude_hotels:
            continue
        try:
            rid = int(float(str(row.supplier_rating_id)))
        except Exception:
            rid = 99
        try:
            rank = preferred.index(rid)
        except Exception:
            rank = 900 + rid

        website = str(row.supplier_website).strip()

        svc_rows = services_df[
            (services_df["supplier_id"].astype(str) == str(row.supplier_id)) &
            (services_df["service_category_id"].astype(str) == acc_cat_id) &
            (services_df["is_active"].astype(str) == "1")
        ]

        seen_names, services_list = set(), []
        for _, sr in svc_rows.iterrows():
            svc_name = str(sr.get("supplier_service_name","")).strip()
            if not svc_name or svc_name.lower() in ("nan","none","null","") or svc_name in seen_names:
                continue
            seen_names.add(svc_name)
            meal  = _resolve(sr.get("meal_plan_id"),     MEAL_PLAN_MAP)
            room  = _resolve(sr.get("room_category_id"), ROOM_CATEGORY_MAP)
            curr  = _resolve(sr.get("currency_id"),      CURRENCY_MAP)
            rate  = _resolve(sr.get("rate_type"),        RATE_TYPE_MAP)
            alloc_raw = sr.get("allocated_rooms")
            try:
                alloc = int(float(alloc_raw)) \
                    if alloc_raw and str(alloc_raw).strip() not in ("nan","None","NULL","") \
                    else None
            except Exception:
                alloc = None
            services_list.append({
                "name":            svc_name,
                "meal_plan":       meal,
                "room_category":   room,
                "currency":        curr,
                "rate_type":       rate,
                "allocated_rooms": alloc,
                "is_active":       "1",
            })

        first = services_list[0] if services_list else {}
        hotels.append({
            "supplier_id":        str(row.supplier_id),
            "name":               name,
            "rating_label":       RATING_MAP.get(str(rid),""),
            "rating_id":          rid,
            "rank":               rank,
            "website":            website if website not in ("nan","None","NULL","") else None,
            "supplier_image":     str(row.supplier_image)  if pd.notna(row.supplier_image)  else "",
            "supplier_image1":    str(row.supplier_image1) if pd.notna(row.supplier_image1) else "",
            "meal_plan_name":     first.get("meal_plan",""),
            "room_category_name": first.get("room_category",""),
            "currency_code":      first.get("currency",""),
            "rate_type":          first.get("rate_type",""),
            "services":           services_list,
        })

    hotels.sort(key=lambda h: h["rank"])
    for h in hotels:
        h.pop("rank")
    return hotels[:max_hotels]

# ================================================================
# 9. FORMAT SERVICE PARAGRAPH
# ================================================================

def format_service_paragraph(service_obj, category_name=None):
    supplier = service_obj.get("supplier",{})
    service  = service_obj.get("service",{})
    def clean(val):
        if not val or str(val).lower() in ("nan","none","null",""):
            return ""
        return str(val)
    sup_name  = clean(supplier.get("supplier_name","")).title()
    svc_name  = clean(service.get("supplier_service_name",""))
    meal_plan = clean(service.get("meal_plan_name",""))
    room_cat  = clean(service.get("room_category_name",""))
    currency  = clean(service.get("currency_code",""))
    ride_type = clean(service.get("ride_type_name",""))
    vehicle   = clean(service.get("vehicle_name",""))
    rate_type = clean(service.get("rate_type",""))
    parts = []
    if svc_name: parts.append(svc_name)
    if sup_name: parts.append(f"at {sup_name}")
    details = []
    if room_cat:  details.append(f"{room_cat} rooms")
    if meal_plan: details.append(f"{meal_plan} meal plan")
    if ride_type: details.append(f"{ride_type} ride")
    if vehicle:   details.append(f"using a {vehicle} vehicle")
    if currency:  details.append(f"priced in {currency}")
    if rate_type: details.append(f"under a {rate_type} rate")
    if details:
        detail_str = ", ".join(details[:-1]) + f" and {details[-1]}" if len(details) > 1 else details[0]
        parts.append(f"which includes {detail_str}")
    if not parts:
        return f"{svc_name or 'Service'} available."
    return " ".join(parts).capitalize() + "."

@app.template_filter('service_description')
def service_description_filter(service_obj):
    return format_service_paragraph(service_obj)

# ================================================================
# 10. GROQ — GENERATE DAY PLAN
# ================================================================

def generate_day_plan(day_num, cities, services_by_city,
                      days, budget, adults, children, travel_style,
                      budget_tier, meal_plan, used_hotels=None, hotel_info=None):
    if used_hotels is None:
        used_hotels = {}
    if hotel_info is None:
        hotel_info  = {}

    city_label = " → ".join(cities)
    multi = len(cities) > 1
    svc_block = ""
    for city in cities:
        svcs = services_by_city.get(city,{})
        if svcs:
            svc_block += f"\n  {city}:\n"
            for cat, data in svcs.items():
                sups = ", ".join(data["suppliers"][:4])
                srvs = ", ".join(data["services"][:3])
                svc_block += f"    [{cat}] → {sups}"
                if srvs:
                    svc_block += f" | options: {srvs}"
                svc_block += "\n"
        else:
            svc_block += f"\n  {city}: No specific services in database.\n"

    pax     = f"{adults} adult(s)" + (f", {children} child(ren)" if children else "")
    bud_str = f"USD {budget} total" if budget else "not specified"

    city_descs = ""
    for city in cities:
        desc = get_city_description(city)
        if desc:
            city_descs += f"  {city}: {desc[:300]}\n"

    accommodation_guidance = ""
    if multi:
        accommodation_guidance = f"\nNOTE: This day covers {len(cities)} cities. Recommend different hotels in each city:"
        for city in cities:
            excluded = used_hotels.get(city,[])
            if excluded:
                accommodation_guidance += f"\n- In {city}, avoid: {', '.join(list(excluded)[:2])}"

    hotel_meal_guidance    = ""
    hotel_names_for_meals  = {}
    for city in cities:
        if city in hotel_info:
            h = hotel_info[city]
            hotel_name = h.get("name","")
            hotel_meal = h.get("meal_plan_name","")
            if hotel_name:
                hotel_names_for_meals[city] = {"name":hotel_name,"meal":hotel_meal}
                hotel_meal_guidance += f"\nFor {city}: Hotel is '{hotel_name}' with '{hotel_meal or 'included meals'}' plan."

    primary_hotel = ""
    if hotel_names_for_meals:
        first_city = cities[0]
        if first_city in hotel_names_for_meals:
            primary_hotel = hotel_names_for_meals[first_city]["name"]
        else:
            primary_hotel = list(hotel_names_for_meals.values())[0]["name"]

    lunch_instruction  = f"Lunch at {primary_hotel}"  if primary_hotel else "Lunch"
    dinner_instruction = f"Dinner at {primary_hotel}" if primary_hotel else "Dinner"

    prompt = f"""
You are a professional Sri Lanka travel planner. Write the Day {day_num} plan for: {city_label}.

TRIP DETAILS:
- Travelers   : {pax}
- Total budget: {bud_str}
- Budget tier : {budget_tier['label']}
- Travel style: {travel_style}
- Meal plan   : {meal_plan}
- Total days  : {days}
{"- NOTE: Travel day covering " + str(len(cities)) + " locations." if multi else ""}

DESTINATION INFO:
{city_descs if city_descs else "  Use general Sri Lanka knowledge."}

ACCOMMODATION (budget tier: {budget_tier['tier']}):
→ Recommend {budget_tier['hotel_quality']} for each city.
{accommodation_guidance}

MEALS:
→ {budget_tier['meal_quality']}
{hotel_meal_guidance}
IMPORTANT: The 1:00 PM lunch and 7:00 PM dinner MUST be served at the hotel property listed above.
Use the exact hotel name in the lunch and dinner lines.

REAL BOOKABLE SERVICES:
{svc_block}

FORMAT — write EXACTLY these 8 lines (no extra lines, no markdown):
🏨 HOTEL: [hotel name, room type, meal plan]
🍽 MEALS: [meals included]
📍 ABOUT: [min 100 words about destinations]
🌅 8:00 AM  — [Activity]: [2-sentence description]
🕙 10:30 AM — [Activity]: [2-sentence description]
🌞 1:00 PM  — {lunch_instruction}: [2 sentences describing what is served at the hotel restaurant]
🌆 4:00 PM  — [Activity]: [2-sentence description]
🍽 7:00 PM  — {dinner_instruction}: [2 sentences describing the evening dining experience at the hotel]

Output ONLY the 8 lines above. No extra text.
"""
    try:
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role":"system","content":"You are a precise Sri Lanka travel planner. Follow the format exactly. Always name the hotel for lunch and dinner entries."},
                {"role":"user",  "content":prompt},
            ],
            temperature=0.5, max_tokens=1200,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"Day plan failed for {city_label}: {e}")
        hotel_name = primary_hotel or cities[0]
        return (
            f"🏨 HOTEL: {budget_tier['hotel_quality'].capitalize()} in {cities[0]}.\n"
            f"🍽 MEALS: {meal_plan} included.\n"
            f"📍 ABOUT: Discover the beauty of {city_label}.\n"
            f"🌅 8:00 AM  — Explore {cities[0]}: Start your day at local attractions.\n"
            f"🕙 10:30 AM — Sightseeing: Visit key landmarks.\n"
            f"🌞 1:00 PM  — Lunch at {hotel_name}: Enjoy authentic Sri Lankan cuisine served at the hotel restaurant.\n"
            f"🌆 4:00 PM  — Leisure time: Relax at your own pace.\n"
            f"🍽 7:00 PM  — Dinner at {hotel_name}: Savour regional flavours at the hotel's dining room."
        )

# ================================================================
# 11. BUILD FULL ITINERARY
# ================================================================

def build_itinerary(days, schedule, user_places, budget, adults, children,
                    travel_style, meal_plan):
    budget_tier = get_budget_tier(budget, days, adults, children)
    user_mentioned_colombo = "colombo" in [norm_city(p) for p in user_places]
    result = []
    used_hotels_per_city = defaultdict(set)

    for i, cities in enumerate(schedule, start=1):
        services_by_city     = {}
        full_services_by_city= {}
        hotel_info           = {}

        for city in cities:
            services_by_city[city] = get_city_services(city)
            full_services_by_city[city] = {
                "rides":               get_city_services_by_category(city,"Ride Types",10),
                "transfers":           get_city_services_by_category(city,"Transfers",10),
                "flight_train":        get_city_services_by_category(city,"Flight \\ Ferry \\ Train",10),
                "driver_guides":       get_city_services_by_category(city,"Driver / Vehicle & Guides",10),
                "additional_expenses": get_city_services_by_category(city,"Additional Expenses",10),
            }
            hotels = fetch_hotel_images(city, tier=budget_tier["tier"], max_hotels=1,
                                        exclude_hotels=used_hotels_per_city[city])
            if hotels:
                hotel_info[city] = hotels[0]

        arrival_note = transfer_note = None
        if i == 1:
            arrival_note = "✈ Arrived at Colombo Bandaranaike International Airport"
            first_city = cities[0]
            if not (user_mentioned_colombo or norm_city(first_city) == "colombo"):
                transfer_note = f"🚌 Transfer from Colombo Airport to {first_city}"

        hotel_images = {}
        for city in cities:
            hotels = fetch_hotel_images(city, tier=budget_tier["tier"], max_hotels=1,
                                        exclude_hotels=used_hotels_per_city[city])
            for hotel in hotels:
                used_hotels_per_city[city].add(hotel["name"])
            hotel_images[city] = hotels

        ai_plan = generate_day_plan(
            day_num=i, cities=cities, services_by_city=services_by_city,
            days=days, budget=budget, adults=adults, children=children,
            travel_style=travel_style, budget_tier=budget_tier, meal_plan=meal_plan,
            used_hotels=used_hotels_per_city, hotel_info=hotel_info,
        )
        result.append({
            "day_num":              i,
            "cities":               cities,
            "city_label":           " → ".join(cities),
            "arrival_note":         arrival_note,
            "transfer_note":        transfer_note,
            "services_by_city":     services_by_city,
            "full_services_by_city":full_services_by_city,
            "hotel_images":         hotel_images,
            "ai_plan":              ai_plan,
            "budget_tier":          budget_tier,
            "is_multi_city":        len(cities) > 1,
        })
    return result

# ================================================================
# 12. IMAGE FETCH
# ================================================================

PLACE_KEYWORDS = {
    "sigiriya":    "Sigiriya Lion Rock fortress aerial Sri Lanka",
    "dambulla":    "Dambulla Cave Temple golden Buddha Sri Lanka",
    "kandy":       "Kandy Temple of Tooth Dalada Maligawa Sri Lanka",
    "nuwara eliya":"Nuwara Eliya tea plantation green hills Sri Lanka",
    "ella":        "Ella Nine Arch Bridge train Sri Lanka",
    "yala":        "Yala National Park leopard safari jeep Sri Lanka",
    "galle":       "Galle Fort lighthouse Dutch colonial Sri Lanka",
    "colombo":     "Colombo city skyline Beira Lake Lotus Tower Sri Lanka",
}

def _place_query(city):
    return PLACE_KEYWORDS.get(norm_city(city), f"{city} Sri Lanka landscape travel")

def _unsplash(query, per_page=3):
    if not UNSPLASH_ACCESS_KEY or UNSPLASH_ACCESS_KEY in ("None",""):
        return []
    try:
        r = requests.get("https://api.unsplash.com/search/photos",
            params={"query":query,"client_id":UNSPLASH_ACCESS_KEY,
                    "per_page":per_page,"orientation":"landscape","content_filter":"high"},
            timeout=8)
        if r.status_code != 200:
            return []
        return [x["urls"]["regular"] for x in r.json().get("results",[])]
    except Exception as e:
        logger.error(f"Unsplash error: {e}"); return []

def _pexels(query, per_page=3):
    if not PEXELS_API_KEY or PEXELS_API_KEY in ("None",""):
        return []
    try:
        r = requests.get("https://api.pexels.com/v1/search",
            headers={"Authorization":PEXELS_API_KEY},
            params={"query":query,"per_page":per_page,"orientation":"landscape"},
            timeout=8)
        if r.status_code != 200:
            return []
        return [p["src"]["large"] for p in r.json().get("photos",[])]
    except Exception as e:
        logger.error(f"Pexels error: {e}"); return []

@lru_cache(maxsize=200)
def fetch_place_image(city):
    for q in [_place_query(city), f"{city} Sri Lanka"]:
        for fn in [_unsplash, _pexels]:
            urls = fn(q, 3)
            if urls:
                return urls[0]
    return None

def _hotel_image(hotel_name, city):
    clean = hotel_name.strip(" -,.")
    for q in [f"{clean} {city} Sri Lanka", f"{clean} Sri Lanka hotel",
              f"{clean} hotel", f"{clean} resort"]:
        for fn in [_unsplash, _pexels]:
            urls = fn(q, 3)
            if urls:
                return urls[0]
    return None

def fetch_hotel_images(city, tier="medium", max_hotels=1, exclude_hotels=None):
    hotels = get_city_hotels_by_tier(city, tier=tier, max_hotels=max_hotels,
                                     exclude_hotels=exclude_hotels)
    result = []
    for hotel in hotels:
        img = str(hotel.get("supplier_image","")).strip().lower()
        image_url = hotel["supplier_image"] \
            if img and img not in ("nan","none","null","") \
            else _hotel_image(hotel["name"], city)
        result.append({
            "supplier_id":        hotel["supplier_id"],
            "name":               hotel["name"],
            "rating_label":       hotel["rating_label"],
            "image_url":          image_url,
            "website":            hotel["website"],
            "meal_plan_name":     hotel.get("meal_plan_name",""),
            "room_category_name": hotel.get("room_category_name",""),
            "currency_code":      hotel.get("currency_code",""),
            "rate_type":          hotel.get("rate_type",""),
            "services":           hotel.get("services",[]),
        })
    return result

# ================================================================
# 13. SERVICE FETCHING
# ================================================================

def get_supplier_by_id(supplier_id):
    if not supplier_id:
        return None
    row = suppliers_df[suppliers_df["supplier_id"].astype(str) == str(supplier_id)]
    if row.empty:
        return None
    r = row.iloc[0]
    def _g(k): return str(r.get(k,"")) if pd.notna(r.get(k)) else ""
    return {
        "supplier_id":        str(r.get("supplier_id","")),
        "supplier_code":      _g("supplier_code"),
        "supplier_name":      _g("supplier_name"),
        "supplier_address":   _g("supplier_address"),
        "supplier_email":     _g("supplier_email"),
        "supplier_telephone": _g("supplier_telephone"),
        "supplier_mobile":    _g("supplier_mobile"),
        "supplier_website":   _g("supplier_website"),
        "supplier_rating_id": _g("supplier_rating_id"),
        "city_id":            _g("city_id"),
        "latitude":           _g("latitude")  or None,
        "longitude":          _g("longitude") or None,
        "supplier_image":     _g("supplier_image")  or None,
        "supplier_image1":    _g("supplier_image1") or None,
    }

def get_city_services_by_category(city, category_name, max_suppliers=10, supplier_id=None):
    mask_city = full_df["city_name"].str.lower() == norm_city(city)
    if category_name:
        mask_cat    = full_df["service_category_name"].str.lower() == category_name.lower()
        df_filtered = full_df[mask_city & mask_cat].copy()
    else:
        df_filtered = full_df[mask_city].copy()
    if df_filtered.empty:
        return []
    if supplier_id:
        df_filtered = df_filtered[df_filtered["supplier_id"].astype(str) == str(supplier_id)]
        if df_filtered.empty:
            return []
    suppliers_grouped = df_filtered.groupby("supplier_id").first().reset_index().head(max_suppliers)
    result = []
    for _, row in suppliers_grouped.iterrows():
        sid_val  = str(row.get("supplier_id",""))
        svc_rows = df_filtered[df_filtered["supplier_id"].astype(str) == sid_val]
        services_list = []
        for _, srow in svc_rows.iterrows():
            def _sid(k): return str(srow.get(k,"")) if k in srow else ""
            meal_plan_name        = _resolve(_sid("meal_plan_id"),        MEAL_PLAN_MAP)
            room_category_name    = _resolve(_sid("room_category_id"),    ROOM_CATEGORY_MAP)
            currency_code         = _resolve(_sid("currency_id"),         CURRENCY_MAP)
            ride_type_name        = _resolve(_sid("ride_type_id"),        RIDE_TYPE_MAP)
            vehicle_category_name = _resolve(_sid("vehicle_category_id"), VEHICLE_CATEGORY_MAP)
            rate_type_label       = _resolve(_sid("rate_type"),           RATE_TYPE_MAP)
            services_list.append({
                "supplier":{
                    "supplier_id":   sid_val,
                    "supplier_name": str(row.get("supplier_name","")),
                    "supplier_address": str(row.get("supplier_address","")),
                    "latitude":  str(row.get("latitude"))  if pd.notna(row.get("latitude"))  else None,
                    "longitude": str(row.get("longitude")) if pd.notna(row.get("longitude")) else None,
                    "city_name": city,
                    "supplier_image":  str(row.get("supplier_image",  "")) if pd.notna(row.get("supplier_image"))  else "",
                    "supplier_image1": str(row.get("supplier_image1", "")) if pd.notna(row.get("supplier_image1")) else "",
                },
                "service":{
                    "supplier_service_id":   str(srow.get("supplier_service_id","")),
                    "supplier_service_name": str(srow.get("supplier_service_name","")),
                    "meal_plan_name":         meal_plan_name,
                    "room_category_name":     room_category_name,
                    "currency_code":          currency_code,
                    "ride_type_name":         ride_type_name,
                    "vehicle_category_name":  vehicle_category_name,
                    "vehicle_name":           "",
                    "rate_type":              rate_type_label,
                }
            })
        unique_services = {}
        for svc in services_list:
            key = svc["service"]["supplier_service_name"].lower()
            if key not in unique_services:
                unique_services[key] = svc
        services_list = sorted(unique_services.values(),
                               key=lambda x: x["service"]["supplier_service_name"].lower())
        if services_list:
            result.append({"service_category_id":str(row.get("service_category_id","")),"services":services_list})
    return result

def get_city_shops(city):
    city_row = city_index.get(norm_city(city))
    if city_row is None:
        return []
    city_id  = str(city_row.get("city_id"))
    city_mask= suppliers_df["city_id"].astype(str) == city_id
    del_mask = suppliers_df["deleted"].astype(str) == "0" if "deleted" in suppliers_df.columns else True
    df = suppliers_df[city_mask & del_mask].copy()
    cat_row = categories_df[categories_df["service_category_name"].str.lower() == "shopping outlets"]
    if cat_row.empty:
        return []
    cat_id = str(cat_row.iloc[0]["service_category_id"])
    shops  = []
    for row in df.itertuples():
        sup_svcs = services_df[
            (services_df["supplier_id"].astype(str) == str(row.supplier_id)) &
            (services_df["service_category_id"].astype(str) == cat_id)
        ]
        if not sup_svcs.empty:
            shops.append({
                "supplier_id":        str(row.supplier_id),
                "supplier_name":      str(row.supplier_name),
                "supplier_address":   str(row.supplier_address),
                "supplier_telephone": str(row.supplier_telephone) if hasattr(row,"supplier_telephone") else "",
                "supplier_mobile":    str(row.supplier_mobile)    if hasattr(row,"supplier_mobile")    else "",
                "latitude":  str(row.latitude)  if pd.notna(row.latitude)  else None,
                "longitude": str(row.longitude) if pd.notna(row.longitude) else None,
            })
    return shops[:3]

def get_city_rides(city, supplier_id=None):
    results = []
    for cat in ["Ride Types","Transport"]:
        results.extend(get_city_services_by_category(city,cat,10,supplier_id))
    return results

def get_city_transfers(city, supplier_id=None):
    return get_city_services_by_category(city,"Transfers",10,supplier_id)

def get_city_flight_train(city, supplier_id=None):
    return get_city_services_by_category(city,"Flight \\ Ferry \\ Train",10,supplier_id)

def get_city_driver_guides(city, supplier_id=None):
    return get_city_services_by_category(city,"Driver / Vehicle & Guides",10,supplier_id)

def get_city_additional_expenses(city, supplier_id=None):
    return get_city_services_by_category(city,"Additional Expenses",10,supplier_id)

def calculate_distance_between_cities(city1, city2):
    r1 = city_index.get(norm_city(city1))
    r2 = city_index.get(norm_city(city2))
    if r1 and r2:
        try:
            return round(haversine(
                (float(r1["latitude"]),float(r1["longitude"])),
                (float(r2["latitude"]),float(r2["longitude"]))
            ))
        except Exception:
            pass
    return None

def get_city_images(city):
    row  = city_index.get(norm_city(city))
    base = f"http://localhost/tripfusion/assets/img/upload/city/{city}"
    if row is None:
        return {"image1":f"{base}/","image2":f"{base}/","image3":f"{base}/"}
    def _img(f):
        return f"{base}/{f}" if f and f not in ("nan","None","NULL") else f"{base}/"
    return {
        "image1":_img(row.get("city_image1","")),
        "image2":_img(row.get("city_image2","")),
        "image3":_img(row.get("city_image3","")),
    }

# ================================================================
# JSON RESPONSE HELPERS
# ================================================================

BASE_SUP_IMG       = "http://localhost/tripfusion/assets/img/upload/supplier/"
BASE_CITY_IMG_ROOT = "http://localhost/tripfusion/assets/img/upload/city"

def _safe(val, fallback=""):
    s = str(val).strip() if val is not None else ""
    return fallback if s.lower() in ("nan","none","null","") else s

def _coord(val):
    try:
        return str(float(str(val).strip()))
    except Exception:
        return None

def _city_img_url(city_name, filename):
    f = _safe(filename)
    return f"{BASE_CITY_IMG_ROOT}/{city_name}/{f}" if f else f"{BASE_CITY_IMG_ROOT}/{city_name}/"

def _sup_img_url(filename):
    f = _safe(filename)
    return f"{BASE_SUP_IMG}{f}" if f else BASE_SUP_IMG

def _build_services_for_json(city, category_name, max_suppliers=2, restrict_supplier_id=None):
    mask_city = full_df["city_name"].str.lower() == norm_city(city)
    mask_cat  = full_df["service_category_name"].str.lower() == category_name.lower()
    df = full_df[mask_city & mask_cat].copy()
    if df.empty:
        return []
    if restrict_supplier_id:
        df = df[df["supplier_id"].astype(str) == str(restrict_supplier_id)]
        if df.empty:
            return []
    supplier_groups = df.groupby("supplier_id").first().reset_index().head(max_suppliers)
    result = []
    for _, row in supplier_groups.iterrows():
        sid    = str(row.get("supplier_id",""))
        cat_id = str(row.get("service_category_id",""))
        city_id= str(row.get("city_id",""))
        sup_obj = {
            "supplier_id":       sid,
            "supplier_name":     _safe(row.get("supplier_name","")),
            "supplier_code":     _safe(row.get("supplier_code","")),
            "supplier_address":  _safe(row.get("supplier_address","")),
            "supplier_email":    _safe(row.get("supplier_email","")),
            "supplier_telephone":_safe(row.get("supplier_telephone","")),
            "supplier_mobile":   _safe(row.get("supplier_mobile","")),
            "supplier_website":  _safe(row.get("supplier_website","")),
            "supplier_image":    _sup_img_url(row.get("supplier_image")),
            "supplier_image1":   _sup_img_url(row.get("supplier_image1")),
            "supplier_rating_id":_safe(str(row.get("supplier_rating_id",""))),
            "city_id":  city_id, "city_name": city,
            "latitude": _coord(row.get("latitude")),
            "longitude":_coord(row.get("longitude")),
        }
        svc_rows = df[df["supplier_id"].astype(str) == sid]
        seen, services = set(), []
        for _, sr in svc_rows.iterrows():
            svc_name = _safe(sr.get("supplier_service_name",""))
            if not svc_name or svc_name in seen:
                continue
            seen.add(svc_name)
            meal_lbl = _resolve(sr.get("meal_plan_id"),        MEAL_PLAN_MAP)
            room_lbl = _resolve(sr.get("room_category_id"),    ROOM_CATEGORY_MAP)
            curr_lbl = _resolve(sr.get("currency_id"),         CURRENCY_MAP)
            rate_lbl = _resolve(sr.get("rate_type"),           RATE_TYPE_MAP)
            ride_lbl = _resolve(sr.get("ride_type_id"),        RIDE_TYPE_MAP)
            vcat_lbl = _resolve(sr.get("vehicle_category_id"), VEHICLE_CATEGORY_MAP)
            meal_id  = _safe(str(sr.get("meal_plan_id","")))
            room_id  = _safe(str(sr.get("room_category_id","")))
            curr_id  = _safe(str(sr.get("currency_id","")))
            ride_id  = _safe(str(sr.get("ride_type_id","")))
            vcat_id  = _safe(str(sr.get("vehicle_category_id","")))
            veh_id   = _safe(str(sr.get("vehicle_id","")))
            rate_raw = _safe(str(sr.get("rate_type","")))
            try:
                alloc_raw = sr.get("allocated_rooms")
                alloc_int = int(float(alloc_raw)) if alloc_raw and _safe(str(alloc_raw)) else None
            except Exception:
                alloc_int = None
            svc_obj = {
                "supplier_service_id":   _safe(str(sr.get("supplier_service_id",""))),
                "supplier_service_name": svc_name,
                "service_category_id":   cat_id,
                "is_active":"1",
                "is_show":  _safe(str(sr.get("is_show",""))),
                "ferry_type":_safe(str(sr.get("ferry_type",""))),
            }
            if meal_id  and meal_id  not in ("nan","none","null"): svc_obj["meal_plan_id"]=meal_id;  svc_obj["meal_plan"]=meal_lbl
            if room_id  and room_id  not in ("nan","none","null"): svc_obj["room_category_id"]=room_id; svc_obj["room_category"]=room_lbl
            if curr_id  and curr_id  not in ("nan","none","null"): svc_obj["currency_id"]=curr_id;  svc_obj["currency"]=curr_lbl
            if rate_raw and rate_raw not in ("nan","none","null"): svc_obj["rate_type_id"]=rate_raw; svc_obj["rate_type"]=rate_lbl
            if ride_id  and ride_id  not in ("nan","none","null"): svc_obj["ride_type_id"]=ride_id;  svc_obj["ride_type"]=ride_lbl
            if vcat_id  and vcat_id  not in ("nan","none","null"): svc_obj["vehicle_category_id"]=vcat_id; svc_obj["vehicle_category"]=vcat_lbl
            if veh_id   and veh_id   not in ("nan","none","null"): svc_obj["vehicle_id"]=veh_id
            if alloc_int: svc_obj["allocated_rooms"]=alloc_int
            services.append({"supplier":sup_obj,"service":svc_obj})
        if services:
            result.append({"service_category_id":cat_id,"services":services})
    return result

def _build_meals_for_json(city, accommodation_supplier_id=None):
    if accommodation_supplier_id:
        hotel_meals = _build_services_for_json(city,"Meals",max_suppliers=1,
                                                restrict_supplier_id=accommodation_supplier_id)
        if hotel_meals:
            return hotel_meals
    return _build_services_for_json(city,"Meals",max_suppliers=2)

def _parse_ai_plan(ai_plan_text):
    schedule   = []
    hotel_line = meals_line = about_text = ""
    for line in ai_plan_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("🏨") or line.startswith("HOTEL"):
            hotel_line = re.sub(r"^🏨\s*HOTEL:\s*","",line).strip()
        elif line.startswith("🍽 MEALS") or line.startswith("MEALS"):
            meals_line = re.sub(r"^🍽\s*MEALS:\s*","",line).strip()
        elif line.startswith("📍") or "ABOUT" in line[:10]:
            about_text = re.sub(r"^📍\s*ABOUT:\s*","",line).strip()
        else:
            parts = line.split(" — ",1)
            if len(parts) == 2:
                time_part = re.sub(r"[🌅🕙🌞🌆🍽🌇🌃]","",parts[0]).strip()
                desc_part = parts[1].strip()
                act_parts = desc_part.split(":",1)
                activity    = act_parts[0].strip() if len(act_parts) > 1 else ""
                description = act_parts[1].strip() if len(act_parts) > 1 else desc_part
                schedule.append({"time":time_part,"activity":activity,"description":description})
    return {"hotel":hotel_line,"meals":meals_line,"about":about_text,"schedule":schedule}

# ================================================================
# JSON RESPONSE
# ================================================================

def generate_json_response(days, schedule, user_places, budget, adults, children,
                           travel_style, meal_plan, itinerary_days=None):
    try:
        budget_tier = get_budget_tier(budget, days, adults, children)
        start_date  = datetime.now().date()
        details     = []
        used_hotels = defaultdict(set)

        tier = budget_tier["tier"]
        if tier == "luxury":
            meal_priority = ["Full Board","Half Board","Bed & Breakfast","All Inclusive","Room Only"]
        elif tier == "budget":
            meal_priority = ["Bed & Breakfast","Room Only","Half Board","Full Board"]
        else:
            meal_priority = ["Half Board","Bed & Breakfast","Full Board","All Inclusive","Room Only"]

        for idx, day_cities in enumerate(schedule):
            date_str   = (start_date + timedelta(days=idx)).strftime("%Y-%m-%d")
            start_city = day_cities[0]
            end_city   = day_cities[-1]
            iday       = None
            if itinerary_days:
                for d in itinerary_days:
                    if d.get("day_num") == idx+1:
                        iday = d; break

            distance = calculate_distance_between_cities(start_city,end_city) \
                if start_city != end_city else None
            sc = city_index.get(norm_city(start_city),{})
            ec = city_index.get(norm_city(end_city),  {})
            sc_imgs = {k:_city_img_url(start_city,sc.get(f"city_image{i}")) for i,k in enumerate(["image1","image2","image3"],1)}
            ec_imgs = {k:_city_img_url(end_city,  ec.get(f"city_image{i}")) for i,k in enumerate(["image1","image2","image3"],1)}

            accommodation = []
            acc_supplier_id = None
            if iday and iday.get("hotel_images",{}).get(start_city):
                h = iday["hotel_images"][start_city][0]
                acc_supplier_id = h.get("supplier_id")
                sup_info = get_supplier_by_id(acc_supplier_id) or {}
                svcs     = h.get("services",[])
                best_svc = None; best_score = 999
                for svc in svcs:
                    mp = svc.get("meal_plan","")
                    if mp in meal_priority:
                        score = meal_priority.index(mp)
                        if score < best_score:
                            best_score = score; best_svc = svc
                if best_svc is None and svcs:
                    best_svc = svcs[0]
                accommodation.append({
                    "supplier":{
                        "supplier_id":        _safe(str(acc_supplier_id)),
                        "supplier_name":      h.get("name",""),
                        "supplier_code":      _safe(sup_info.get("supplier_code","")),
                        "supplier_address":   _safe(sup_info.get("supplier_address","")),
                        "supplier_email":     _safe(sup_info.get("supplier_email","")),
                        "supplier_telephone": _safe(sup_info.get("supplier_telephone","")),
                        "supplier_mobile":    _safe(sup_info.get("supplier_mobile","")),
                        "supplier_website":   h.get("website") or "",
                        "supplier_image":     h.get("image_url") or BASE_SUP_IMG,
                        "supplier_image1":    h.get("image_url") or BASE_SUP_IMG,
                        "supplier_rating_id": _safe(str(sup_info.get("supplier_rating_id",""))),
                        "rating_label":       h.get("rating_label",""),
                        "city_id":            _safe(str(sc.get("city_id",""))),
                        "city_name":          start_city,
                        "latitude":           _coord(sup_info.get("latitude")),
                        "longitude":          _coord(sup_info.get("longitude")),
                    },
                    "service": best_svc,
                })
            else:
                hotels = fetch_hotel_images(start_city,tier=budget_tier["tier"],
                                            max_hotels=1,exclude_hotels=used_hotels[start_city])
                if hotels:
                    h = hotels[0]; acc_supplier_id = h["supplier_id"]
                    used_hotels[start_city].add(h["name"])
                    sup_info = get_supplier_by_id(acc_supplier_id) or {}
                    svcs     = h.get("services",[])
                    best_svc = next((s for s in svcs if s.get("meal_plan") in meal_priority),
                                    svcs[0] if svcs else None)
                    accommodation.append({
                        "supplier":{
                            "supplier_id":        _safe(str(acc_supplier_id)),
                            "supplier_name":      h["name"],
                            "supplier_code":      _safe(sup_info.get("supplier_code","")),
                            "supplier_address":   _safe(sup_info.get("supplier_address","")),
                            "supplier_email":     _safe(sup_info.get("supplier_email","")),
                            "supplier_telephone": _safe(sup_info.get("supplier_telephone","")),
                            "supplier_mobile":    _safe(sup_info.get("supplier_mobile","")),
                            "supplier_website":   h.get("website") or "",
                            "supplier_image":     h.get("image_url") or BASE_SUP_IMG,
                            "supplier_image1":    h.get("image_url") or BASE_SUP_IMG,
                            "supplier_rating_id": _safe(str(sup_info.get("supplier_rating_id",""))),
                            "rating_label":       h.get("rating_label",""),
                            "city_id":            _safe(str(sc.get("city_id",""))),
                            "city_name":          start_city,
                            "latitude":           _coord(sup_info.get("latitude")),
                            "longitude":          _coord(sup_info.get("longitude")),
                        },
                        "service": best_svc,
                    })

            arrival_note  = iday.get("arrival_note")  if iday else None
            transfer_note = iday.get("transfer_note") if iday else None
            ai_plan_raw   = iday.get("ai_plan","")    if iday else ""
            ai_plan_parsed= _parse_ai_plan(ai_plan_raw) if ai_plan_raw else {}

            meals         = _build_meals_for_json(start_city, acc_supplier_id)
            entrances     = _build_services_for_json(start_city,"Entrance Fees",2)
            rides         = _build_services_for_json(start_city,"Ride Types",2)
            transport     = _build_services_for_json(start_city,"Transport",1)
            transfers     = _build_services_for_json(start_city,"Transfers",1)
            flight_train  = _build_services_for_json(start_city,"Flight \\ Ferry \\ Train",1)
            driver_guides = _build_services_for_json(start_city,"Driver / Vehicle & Guides",1)
            additional    = _build_services_for_json(start_city,"Additional Expenses",1)
            shops         = get_city_shops(end_city)

            route = {"city":{"city_id":_safe(str(ec.get("city_id",""))),
                             "city_name":end_city,
                             "latitude": _coord(ec.get("latitude")),
                             "longitude":_coord(ec.get("longitude")),
                             "shops":shops[:5]}}
            if idx == 0:
                route["tour_destination_progress"] = {
                    "status":"reached","reached_at":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "driver_latitude":"0.360000","driver_longitude":"26.000000",
                }

            details.append({
                "day":str(idx+1),"date":date_str,"distance":str(distance) if distance else None,
                "arrival_note":arrival_note,"transfer_note":transfer_note,
                "start_city_name":start_city,"start_city_description":get_city_description(start_city),
                "start_city_image1":sc_imgs["image1"],"start_city_image2":sc_imgs["image2"],"start_city_image3":sc_imgs["image3"],
                "start_latitude":_coord(sc.get("latitude")),"start_longitude":_coord(sc.get("longitude")),
                "end_city_name":end_city,"end_city_description":get_city_description(end_city),
                "end_city_image1":ec_imgs["image1"],"end_city_image2":ec_imgs["image2"],"end_city_image3":ec_imgs["image3"],
                "end_latitude":_coord(ec.get("latitude")),"end_longitude":_coord(ec.get("longitude")),
                "route":route,"accommodation":accommodation,"day_plan":ai_plan_parsed,
                "entrances":entrances,"meals":meals,"rides":rides,"transport":transport,
                "transfers":transfers,"flight_train":flight_train,"driver_guides":driver_guides,
                "additional_expenses":additional,"tour_day_progress":None,
            })

        return {
            "status":200,"message":"Tour Details",
            "data":{
                "customer_name":None,"mobile":None,"assign_tour_id":"1",
                "budget_tier":budget_tier,"total_days":days,
                "total_travelers":adults+children,"adults":adults,"children":children,
                "travel_style":travel_style,"meal_plan":meal_plan,
                "total_budget":budget,"details":details,
            },
        }
    except Exception as e:
        logger.error(f"Failed to generate JSON response: {e}")
        import traceback; traceback.print_exc()
        return {"status":500,"message":str(e),"data":None}

# ================================================================
# REGENERATE DAYS — helper functions
# ================================================================

def _build_regen_prompt(day_num, cities, user_instruction,
                        days, budget, adults, children,
                        travel_style, budget_tier, meal_plan,
                        services_by_city, hotel_info):
    city_label = " → ".join(cities)
    pax        = f"{adults} adult(s)" + (f", {children} child(ren)" if children else "")
    bud_str    = f"USD {budget} total" if budget else "not specified"

    city_descs = ""
    for city in cities:
        desc = get_city_description(city)
        if desc:
            city_descs += f"  {city}: {desc[:300]}\n"

    svc_block = ""
    for city in cities:
        svcs = services_by_city.get(city, {})
        if svcs:
            svc_block += f"\n  {city}:\n"
            for cat, data in svcs.items():
                sups = ", ".join(data["suppliers"][:4])
                svc_block += f"    [{cat}] → {sups}\n"

    hotel_meal_guidance = ""
    primary_hotel = ""
    for city in cities:
        if city in hotel_info:
            h     = hotel_info[city]
            hname = h.get("name","")
            hmeal = h.get("meal_plan_name","")
            if hname:
                if not primary_hotel:
                    primary_hotel = hname
                hotel_meal_guidance += f"\nFor {city}: Hotel is '{hname}' with '{hmeal or 'meals included'}' plan."

    lunch_instruction  = f"Lunch at {primary_hotel}"  if primary_hotel else "Lunch"
    dinner_instruction = f"Dinner at {primary_hotel}" if primary_hotel else "Dinner"

    return f"""
You are a professional Sri Lanka travel planner. Modify the Day {day_num} plan for: {city_label}.

USER MODIFICATION REQUEST:
"{user_instruction}"

Apply this request while keeping the trip coherent.

TRIP DETAILS:
- Travelers   : {pax}
- Total budget: {bud_str}
- Budget tier : {budget_tier['label']}
- Travel style: {travel_style}
- Meal plan   : {meal_plan}
- Total days  : {days}

DESTINATION INFO:
{city_descs if city_descs else '  Use general Sri Lanka knowledge.'}

ACCOMMODATION:
{hotel_meal_guidance if hotel_meal_guidance else f"Recommend {budget_tier['hotel_quality']}."}
IMPORTANT: The 1:00 PM lunch and 7:00 PM dinner MUST be at the hotel listed above.

AVAILABLE SERVICES:
{svc_block if svc_block else '  Use general Sri Lanka knowledge for activities.'}

FORMAT — write EXACTLY these 8 lines (no extra lines, no markdown):
🏨 HOTEL: [hotel name, room type, meal plan]
🍽 MEALS: [meals included]
📍 ABOUT: [min 100 words about destinations incorporating the user modification]
🌅 8:00 AM  — [Activity]: [2-sentence description reflecting user request]
🕙 10:30 AM — [Activity]: [2-sentence description]
🌞 1:00 PM  — {lunch_instruction}: [2 sentences describing what is served at the hotel]
🌆 4:00 PM  — [Activity]: [2-sentence description reflecting user request]
🍽 7:00 PM  — {dinner_instruction}: [2 sentences describing evening dining at the hotel]

Output ONLY the 8 lines above. No extra text.
"""

def _fallback_regen_plan(cities, budget_tier, meal_plan, hotel_info):
    primary = next(
        (hotel_info[c]["name"] for c in cities if c in hotel_info),
        cities[0] if cities else "Hotel",
    )
    return (
        f"🏨 HOTEL: {budget_tier['hotel_quality'].capitalize()} in {cities[0] if cities else 'city'}.\n"
        f"🍽 MEALS: {meal_plan} included.\n"
        f"📍 ABOUT: Discover the beauty of {', '.join(cities)}.\n"
        f"🌅 8:00 AM  — Morning Explore: Start your day at local attractions and key landmarks.\n"
        f"🕙 10:30 AM — Sightseeing: Visit scenic spots and cultural sites in the area.\n"
        f"🌞 1:00 PM  — Lunch at {primary}: Enjoy a curated Sri Lankan meal at the hotel restaurant.\n"
        f"🌆 4:00 PM  — Leisure Activity: Relax or join a local guided experience.\n"
        f"🍽 7:00 PM  — Dinner at {primary}: Savour regional flavours in the hotel dining room."
    )

# ================================================================
# SHARED HELPER — load stored itinerary and render a template
# ================================================================

def _render_itinerary(template_name):
    """Load itinerary from temp file (or session fallback) and render the given template."""
    itinerary_id = session.get("itinerary_id")
    if not itinerary_id:
        return redirect(url_for("index"))

    itinerary_file = os.path.join(tempfile.gettempdir(), f"itinerary_{itinerary_id}.json")
    if not os.path.exists(itinerary_file):
        return redirect(url_for("index"))

    with open(itinerary_file, "r", encoding="utf-8") as f:
        full_data = json.load(f)

    days         = full_data["days"]
    budget       = full_data.get("budget")
    adults       = full_data.get("adults", 1)
    children     = full_data.get("children", 0)
    travel_style = full_data.get("travel_style", "General Sightseeing")
    meal_plan    = full_data.get("meal_plan", "Breakfast and Dinner")
    places       = full_data.get("places", [])
    schedule     = full_data.get("schedule", [])
    itinerary_days_stored = full_data.get("itinerary_days", [])

    budget_tier   = get_budget_tier(budget, days, adults, children)
    unique_cities = list(dict.fromkeys(c for dc in schedule for c in dc))
    route_cities  = []
    for dc in schedule:
        for city in dc:
            if not route_cities or route_cities[-1] != city:
                route_cities.append(city)

    hero_images, seen = [], set()
    for day_cities in schedule:
        for city in day_cities:
            if city not in seen:
                seen.add(city)
                hero_images.append({"place": city, "url": fetch_place_image(city)})

    header_data = {
        "title":          "Your Sri Lanka Journey",
        "subtitle":       "A journey crafted for you",
        "days":           days,
        "budget":         budget,
        "budget_tier":    budget_tier,
        "adults":         adults,
        "children":       children,
        "travel_style":   travel_style,
        "meal_plan":      meal_plan,
        "total_cities":   len(unique_cities),
        "total_travelers":adults + children,
        "route_cities":   route_cities,
        "route_display":  " → ".join(route_cities),
        "hero_images":    hero_images,
    }

    return render_template(
        template_name,
        header_data=header_data,
        itinerary_days=itinerary_days_stored,
        images=hero_images,
        days=days,
        budget=budget,
        budget_tier=budget_tier,
        adults=adults,
        children=children,
        travel_style=travel_style,
        meal_plan=meal_plan,
        schedule=schedule,
    )

# ================================================================
# FLASK ROUTES
# ================================================================

@app.route("/", methods=["GET","POST"])
def index():
    if request.method == "POST":
        try:
            email_text = request.form.get("email","").strip()
            if not email_text:
                return "Email content is required", 400

            days, budget, adults, children, places, travel_style, meal_plan = \
                extract_trip_info_groq(email_text)
            budget_tier = get_budget_tier(budget, days, adults, children)
            schedule    = build_schedule(days, places)
            itinerary_days = build_itinerary(
                days=days, schedule=schedule, user_places=places,
                budget=budget, adults=adults, children=children,
                travel_style=travel_style, meal_plan=meal_plan,
            )

            hero_images, seen = [], set()
            for day_cities in schedule:
                for city in day_cities:
                    if city not in seen:
                        seen.add(city)
                        hero_images.append({"place":city,"url":fetch_place_image(city)})

            unique_cities = list(dict.fromkeys(c for dc in schedule for c in dc))
            route_cities  = []
            for dc in schedule:
                for city in dc:
                    if not route_cities or route_cities[-1] != city:
                        route_cities.append(city)

            # Serialise itinerary days for temp file storage
            serialisable_days = []
            for d in itinerary_days:
                serialisable_days.append({
                    "day_num":               d["day_num"],
                    "cities":                d["cities"],
                    "city_label":            d["city_label"],
                    "arrival_note":          d["arrival_note"],
                    "transfer_note":         d["transfer_note"],
                    "hotel_images":          d["hotel_images"],
                    "full_services_by_city": d["full_services_by_city"],
                    "ai_plan":               d["ai_plan"],
                    "budget_tier":           d["budget_tier"],
                    "is_multi_city":         d["is_multi_city"],
                })

            full_itinerary_data = {
                "days":           days,
                "budget":         budget,
                "adults":         adults,
                "children":       children,
                "travel_style":   travel_style,
                "meal_plan":      meal_plan,
                "places":         places,
                "schedule":       schedule,
                "itinerary_days": serialisable_days,
            }

            itinerary_id   = str(uuid.uuid4())
            itinerary_file = os.path.join(tempfile.gettempdir(), f"itinerary_{itinerary_id}.json")
            with open(itinerary_file, "w", encoding="utf-8") as f:
                json.dump(full_itinerary_data, f, ensure_ascii=False)

            session["itinerary_id"]   = itinerary_id
            session["itinerary_data"] = {
                "days":         days,
                "budget":       budget,
                "adults":       adults,
                "children":     children,
                "travel_style": travel_style,
                "meal_plan":    meal_plan,
                "places":       places,
                "schedule":     schedule,
            }

            # Redirect to the classic template (avoids double-render on refresh)
            return redirect(url_for("itinerary_template1"))

        except Exception as e:
            logger.error(f"Error processing itinerary: {e}")
            import traceback; traceback.print_exc()
            return "An internal error occurred. Please check the console for details.", 500

    return render_template("index.html")


# ── Three itinerary template routes ─────────────────────────────

@app.route("/itinerary/classic")
def itinerary_template1():
    return _render_itinerary("itinerary.html")

@app.route("/itinerary/magazine")
def itinerary_template2():
    return _render_itinerary("itinerary2.html")

@app.route("/itinerary/timeline")
def itinerary_template3():
    return _render_itinerary("itinerary3.html")


@app.route("/download_json", methods=["GET"])
def download_json():
    try:
        data = session.get("itinerary_data")
        if not data:
            return {"error":"No itinerary data found. Please generate an itinerary first."}, 404

        itinerary_days = None
        itinerary_id   = session.get("itinerary_id")
        if itinerary_id:
            itinerary_file = os.path.join(tempfile.gettempdir(), f"itinerary_{itinerary_id}.json")
            if os.path.exists(itinerary_file):
                try:
                    with open(itinerary_file,"r",encoding="utf-8") as f:
                        full_data = json.load(f)
                    itinerary_days = full_data.get("itinerary_days")
                    if full_data.get("schedule"):
                        data = full_data
                except Exception as e:
                    logger.warning(f"Could not load itinerary file: {e}")

        json_data = generate_json_response(
            days=data["days"], schedule=data["schedule"], user_places=data["places"],
            budget=data["budget"], adults=data["adults"], children=data["children"],
            travel_style=data["travel_style"], meal_plan=data["meal_plan"],
            itinerary_days=itinerary_days,
        )
        response = app.response_class(
            response=json.dumps(json_data, indent=2, ensure_ascii=False),
            status=200, mimetype="application/json",
        )
        response.headers["Content-Disposition"] = "attachment; filename=itinerary.json"
        return response
    except Exception as e:
        logger.error(f"JSON download failed: {e}")
        return {"error":str(e)}, 500


@app.route("/api/itinerary", methods=["POST"])
def api_itinerary():
    try:
        data = request.get_json()
        if not data or not data.get("email"):
            return jsonify({"status":400,"message":"Email text is required","data":None}), 400
        email_text = data.get("email","").strip()
        days, budget, adults, children, places, travel_style, meal_plan = \
            extract_trip_info_groq(email_text)
        schedule  = build_schedule(days, places)
        json_data = generate_json_response(
            days=days, schedule=schedule, user_places=places,
            budget=budget, adults=adults, children=children,
            travel_style=travel_style, meal_plan=meal_plan,
        )
        return jsonify(json_data)
    except Exception as e:
        logger.error(f"API endpoint failed: {e}")
        return jsonify({"status":500,"message":str(e),"data":None}), 500


# ================================================================
# REGENERATE DAYS
# ================================================================

@app.route("/api/regenerate_days", methods=["POST"])
def regenerate_days():
    try:
        body = request.get_json(force=True, silent=True)
        if not body:
            return jsonify({"status":400,"message":"No JSON body provided"}), 400

        selected_days = [int(d) for d in body.get("selected_days",[])]
        user_prompt   = str(body.get("user_prompt","")).strip()
        itinerary_id  = str(body.get("itinerary_id","")).strip()

        logger.info(f"regenerate_days: days={selected_days}, id={itinerary_id!r}, prompt={user_prompt!r}")

        if not selected_days:
            return jsonify({"status":400,"message":"No days selected"}), 400
        if not user_prompt:
            return jsonify({"status":400,"message":"No modification prompt provided"}), 400

        # ── Load itinerary ────────────────────────────────────────
        data = None
        itinerary_days_stored = None

        if itinerary_id:
            itinerary_file = os.path.join(tempfile.gettempdir(), f"itinerary_{itinerary_id}.json")
            if os.path.exists(itinerary_file):
                try:
                    with open(itinerary_file,"r",encoding="utf-8") as f:
                        full_data = json.load(f)
                    data = full_data
                    itinerary_days_stored = full_data.get("itinerary_days",[])
                    logger.info(f"Loaded from file: {itinerary_file}")
                except Exception as e:
                    logger.warning(f"Could not read itinerary file: {e}")

        if data is None:
            data = session.get("itinerary_data")
            if data:
                logger.info("Loaded itinerary from session")
            else:
                return jsonify({
                    "status":404,
                    "message":"Itinerary data not found. Please generate the itinerary again.",
                }), 404

        # ── Extract fields ────────────────────────────────────────
        days_total   = int(data.get("days",7))
        budget       = data.get("budget")
        adults       = int(data.get("adults",1))
        children     = int(data.get("children",0))
        travel_style = str(data.get("travel_style","General Sightseeing"))
        meal_plan    = str(data.get("meal_plan","Breakfast and Dinner"))
        schedule     = data.get("schedule",[])

        if not schedule:
            return jsonify({"status":400,"message":"Itinerary schedule is empty."}), 400

        budget_tier = get_budget_tier(budget, days_total, adults, children)

        # ── Regenerate selected days ──────────────────────────────
        updated_days = {}

        for day_num in selected_days:
            day_idx = day_num - 1
            if day_idx < 0 or day_idx >= len(schedule):
                logger.warning(f"Day {day_num} out of range, skipping.")
                continue

            cities = schedule[day_idx]
            if isinstance(cities, str):
                cities = [cities]

            logger.info(f"Regenerating day {day_num}: {cities}")

            services_by_city = {}
            hotel_info       = {}

            for city in cities:
                try:
                    services_by_city[city] = get_city_services(city)
                except Exception as e:
                    logger.warning(f"get_city_services failed for {city}: {e}")
                    services_by_city[city] = {}
                try:
                    hotels = fetch_hotel_images(city, tier=budget_tier["tier"], max_hotels=1)
                    if hotels:
                        hotel_info[city] = hotels[0]
                except Exception as e:
                    logger.warning(f"fetch_hotel_images failed for {city}: {e}")

            # Build prompt and call Groq
            try:
                prompt = _build_regen_prompt(
                    day_num=day_num, cities=cities,
                    user_instruction=user_prompt,
                    days=days_total, budget=budget,
                    adults=adults, children=children,
                    travel_style=travel_style,
                    budget_tier=budget_tier, meal_plan=meal_plan,
                    services_by_city=services_by_city, hotel_info=hotel_info,
                )
                resp = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {"role":"system","content":(
                            "You are a precise Sri Lanka travel planner. "
                            "Modify the itinerary day based on the user's request. "
                            "Follow the format exactly. Always name the hotel for lunch and dinner."
                        )},
                        {"role":"user","content":prompt},
                    ],
                    temperature=0.6, max_tokens=1200,
                )
                new_ai_plan = resp.choices[0].message.content.strip()
                logger.info(f"Groq returned plan for day {day_num} ({len(new_ai_plan)} chars)")

            except Exception as e:
                logger.error(f"Groq error for day {day_num}: {e}")
                new_ai_plan = _fallback_regen_plan(cities, budget_tier, meal_plan, hotel_info)

            # Hotel images for response
            hotel_images_out = {}
            for city in cities:
                try:
                    hotel_images_out[city] = fetch_hotel_images(
                        city, tier=budget_tier["tier"], max_hotels=1
                    )
                except Exception as e:
                    logger.warning(f"hotel images failed for {city}: {e}")
                    hotel_images_out[city] = []

            updated_days[str(day_num)] = {
                "day_num":       day_num,
                "cities":        cities,
                "city_label":    " → ".join(cities),
                "ai_plan":       new_ai_plan,
                "hotel_images":  hotel_images_out,
                "budget_tier":   budget_tier,
                "is_multi_city": len(cities) > 1,
            }

            # Persist back into stored days
            if itinerary_days_stored:
                for stored_day in itinerary_days_stored:
                    if int(stored_day.get("day_num",-1)) == day_num:
                        stored_day["ai_plan"]      = new_ai_plan
                        stored_day["hotel_images"] = hotel_images_out
                        break

        if not updated_days:
            return jsonify({"status":400,"message":"No valid days were regenerated."}), 400

        # ── Persist back to temp file ─────────────────────────────
        if itinerary_id and itinerary_days_stored:
            try:
                itinerary_file = os.path.join(tempfile.gettempdir(), f"itinerary_{itinerary_id}.json")
                if os.path.exists(itinerary_file):
                    with open(itinerary_file,"r",encoding="utf-8") as f:
                        saved = json.load(f)
                    saved["itinerary_days"] = itinerary_days_stored
                    with open(itinerary_file,"w",encoding="utf-8") as f:
                        json.dump(saved, f, ensure_ascii=False)
                    logger.info(f"Updated itinerary file id={itinerary_id}")
            except Exception as e:
                logger.warning(f"Could not update itinerary file: {e}")

        return jsonify({
            "status":200,
            "message":f"Successfully regenerated {len(updated_days)} day(s).",
            "updated_days":updated_days,
        })

    except Exception as e:
        logger.error(f"regenerate_days UNHANDLED ERROR: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"status":500,"message":f"Server error: {str(e)}"}), 500


# ================================================================
if __name__ == "__main__":
    app.run(debug=True)