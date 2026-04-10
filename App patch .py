# ================================================================
# app.py  – PATCH INSTRUCTIONS
#
# The 404 error means Flask never registered /api/regenerate_days.
# Follow the three steps below to fix it.
# ================================================================


# ─────────────────────────────────────────────────────────────────
# STEP 1 ── Add this import near the TOP of app.py,
#            right after your other imports (Flask, os, json …)
# ─────────────────────────────────────────────────────────────────

from regenerate import regenerate_bp          # <── ADD THIS LINE


# ─────────────────────────────────────────────────────────────────
# STEP 2 ── Register the blueprint immediately after you create
#            the Flask app object, e.g.:
#
#   app = Flask(__name__)
#   app.register_blueprint(regenerate_bp)    # <── ADD THIS LINE
#
# That is ALL that is needed in app.py itself.
# The route /api/regenerate_days lives inside regenerate.py.
# ─────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────
# STEP 3 ── Make sure these five names are importable from app.py
#            (regenerate.py calls them via _imports()).
#            They almost certainly already exist – just verify:
#
#   client              – your Groq / OpenAI client instance
#   get_budget_tier()   – returns budget-tier dict
#   get_city_description() – returns a text description for a city
#   get_city_services() – returns services dict for a city
#   fetch_hotel_images() – returns list of hotel dicts
# ─────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────
# LOOKUP MAP HELPERS (paste at top of app.py if not already there)
# ─────────────────────────────────────────────────────────────────

MEAL_PLAN_MAP = {
    "1": "Room Only", "2": "Bed & Breakfast", "3": "Half Board",
    "4": "Full Board", "7": "All Inclusive", "9": "Room Only", "10": "Full Board",
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
    "156":"Cabin Room","157":"Marsh Room (No Pool)","158":"Paddy Marsh (With Pool)",
    "162":"Club Lodge","163":"Deluxe Villa","164":"Garden Villa","165":"Family Bungalow",
    "166":"Premium Deluxe","167":"Deluxe Family Residence","168":"Premium Deluxe Spa Suite",
    "169":"Deluxe City View","170":"Beach Studio","171":"Waterfront Chalet",
    "172":"Superior Sea View","173":"Ocean Studio","180":"Loft",
    "181":"Kalkudah Studio","182":"Pasikudah Studio","183":"Pool Chalet",
    "184":"Nilaveli Studio","185":"Anilana Studio","186":"Garden Deluxe",
    "187":"Theme Suite","188":"Lagoon Cabana","192":"Balcony Room",
    "194":"Beach Cabana","197":"Wooden Cabana","199":"Camping Tent",
    "200":"Classic","201":"Deluxe Delight","209":"Tree House",
    "210":"Semi-Luxury Tent","213":"Grand Apartment","222":"Garden Chalet",
    "226":"Amangalla Suite","228":"Luxury Tented Suite","244":"Full Villa",
    "248":"Superior Pool Terrace","249":"Villa Sea View","251":"Beach Villa",
    "252":"Bay Suite","254":"Chalet Villa","255":"Superior Chalet",
    "256":"Deluxe Chalet","257":"Luxury Tent","263":"Superior Family Room",
    "267":"Deluxe Tent","270":"Villa with Jacuzzi","271":"Villa with Plunge Pool",
    "272":"Deluxe Poolside Terrace","273":"Family Residence","274":"Honeymoon Deluxe",
    "276":"Jacuzzi Suite","277":"Plunge Pool Suite","278":"Family & Honeymoon Hut",
    "282":"Tent","285":"Superior Mountain View","293":"2-Bedroom Villa",
    "294":"Luxury Garden Chalet","295":"Courtyard Suite","296":"Premium Suite",
    "297":"Apartment Suite","305":"Bedroom","306":"Cabana","307":"Villa",
    "311":"Superior Lodge","315":"Anilana Lux Suite","316":"Anilana Deluxe Ocean View",
    "319":"Siyambala Tent","320":"Andara Chalet","321":"Kohomba Chalet",
    "334":"Palm Suite","335":"Beach Leisure Suite","336":"Beach Balcony Suite",
    "337":"Beach Access Terrace Suite","338":"Lounge Pool Master Suite",
    "346":"Large Sea View","348":"Beach Suite","349":"Family Villa",
    "350":"Beach Suite with Pool","355":"1 Bedroom Apartment","356":"2 Bedroom Apartment",
    "357":"Cabana Single","359":"Beach Side","360":"Land Side",
    "361":"Luxury AC Room","362":"Standard Suite","363":"Deluxe Sea View with Balcony",
    "366":"Ulagalla Chalet with Pool","387":"Suite","400":"Premier",
    "401":"Deluxe Garden","408":"Comfort Tent","417":"Premier Residence",
    "418":"Grand Residence","446":"Lake View Suite","447":"Premier Golf Suite",
    "448":"Premier Ocean Suite","453":"Solo Suite","454":"Deluxe Lagoon View",
    "455":"Deluxe Pool Side","456":"One Bedroom Ocean View Suite",
    "458":"One Bedroom Garden Pool Villa","459":"Presidential Pool Suite",
    "466":"Bawa Suite","469":"King Villa","470":"Queen Villa","471":"Gem Suite",
    "477":"Luxury Tent","478":"Club Room","479":"Dwelling without Plunge Pool",
    "480":"Dwelling with Plunge Pool","481":"Randholee Suite","482":"Plantation Suite",
    "485":"Boutique Luxury","486":"King Suite Ocean View","487":"Suite with Garden View",
    "488":"Deluxe Family Suite","489":"Deluxe Terrace Ocean View",
    "490":"Grand Deluxe Ocean View","491":"One Bedroom Suite",
    "498":"Suite with Plunge Pool","499":"Bay View Pool Suite",
    "501":"Mountain View Chalet","505":"Deluxe Villa",
    "507":"Duplex Villa with Plunge Pool","509":"Kandyan Suite",
    "511":"Premium Family Villa with Pool","529":"Heritage Suite",
    "530":"Grand Suite","531":"Tower Room",
}
CURRENCY_MAP  = {"0":"LKR","1":"USD","2":"USD","3":"EUR","5":"GBP","8":"AUD","9":"LKR"}
RATE_TYPE_MAP = {"1":"Fixed Rate","2":"Per Person","3":"Per Vehicle"}
RIDE_TYPE_MAP = {"0":"Standard","1":"Jeep","2":"Boat","3":"Boat","4":"Train"}
VEHICLE_CATEGORY_MAP = {
    "1":"Car","3":"Van","4":"Micro Van","5":"33-Seater Coach",
    "6":"Large Coach","7":"Baggage Van","8":"Mini Coach",
    "9":"KDH High Roof Van","10":"SUV",
}

# Keep old names alive so existing code doesn't break
meal_plan_dict        = MEAL_PLAN_MAP
room_category_dict    = ROOM_CATEGORY_MAP
currency_dict         = CURRENCY_MAP
ride_type_dict        = RIDE_TYPE_MAP
vehicle_category_dict = VEHICLE_CATEGORY_MAP
vehicle_dict          = {}


def _resolve(val, mapping):
    """Convert raw float/int/str ID → human-readable label."""
    if val is None:
        return ""
    s = str(val).strip()
    if s.lower() in ("nan", "none", "null", ""):
        return ""
    try:
        s = str(int(float(s)))
    except (ValueError, TypeError):
        return s
    return mapping.get(s, "")


# ─────────────────────────────────────────────────────────────────
# get_city_hotels_by_tier  (replace existing version)
# ─────────────────────────────────────────────────────────────────

def get_city_hotels_by_tier(city, tier="medium", max_hotels=1, exclude_hotels=None):
    import pandas as pd
    if exclude_hotels is None:
        exclude_hotels = set()
    preferred = TIER_RATING_PREFERENCE.get(tier, TIER_RATING_PREFERENCE["medium"])
    mask_city          = full_df["city_name"].str.lower() == norm_city(city)
    mask_accommodation = full_df["service_category_name"] == "Accommodation"

    df_hotels = full_df[mask_city & mask_accommodation][
        ["supplier_id","supplier_name","supplier_rating_id",
         "supplier_website","supplier_image","supplier_image1"]
    ].drop_duplicates("supplier_id").copy()

    acc_cat_row = categories_df[
        categories_df["service_category_name"].str.lower() == "accommodation"
    ]
    acc_cat_id = str(acc_cat_row.iloc[0]["service_category_id"]) if not acc_cat_row.empty else "2"

    hotels = []
    for row in df_hotels.itertuples():
        name = str(row.supplier_name).strip()
        if name in exclude_hotels or not name or name in ("nan","None","NULL",""):
            continue
        try:
            rid  = int(float(str(row.supplier_rating_id)))
        except Exception:
            rid  = 99
        try:
            rank = preferred.index(rid)
        except Exception:
            rank = 900 + rid

        website = str(row.supplier_website).strip()

        svc_rows = services_df[
            (services_df["supplier_id"].astype(str) == str(row.supplier_id)) &
            (services_df["service_category_id"].astype(str) == acc_cat_id) &
            (services_df["is_active"].astype(str) == "1")
        ].copy()

        seen_names    = set()
        services_list = []
        for _, sr in svc_rows.iterrows():
            svc_name = str(sr.get("supplier_service_name","")).strip()
            if not svc_name or svc_name in ("nan","None","NULL","") or svc_name in seen_names:
                continue
            seen_names.add(svc_name)
            meal  = _resolve(sr.get("meal_plan_id"),     MEAL_PLAN_MAP)
            room  = _resolve(sr.get("room_category_id"), ROOM_CATEGORY_MAP)
            curr  = _resolve(sr.get("currency_id"),      CURRENCY_MAP)
            rate  = _resolve(sr.get("rate_type"),        RATE_TYPE_MAP)
            alloc = sr.get("allocated_rooms")
            alloc = int(float(alloc)) if alloc and str(alloc).strip() not in ("nan","None","NULL","") else None
            services_list.append({
                "name":            svc_name,
                "meal_plan":       meal,
                "room_category":   room,
                "currency":        curr,
                "rate_type":       rate,
                "allocated_rooms": alloc,
                "is_active":       str(sr.get("is_active","")).strip(),
            })

        first = services_list[0] if services_list else {}

        hotels.append({
            "supplier_id":        str(row.supplier_id),
            "name":               name,
            "rating_label":       RATING_MAP.get(str(rid), ""),
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


def fetch_hotel_images(city, tier="medium", max_hotels=1, exclude_hotels=None):
    hotels = get_city_hotels_by_tier(
        city, tier=tier, max_hotels=max_hotels, exclude_hotels=exclude_hotels
    )
    result = []
    for hotel in hotels:
        img = str(hotel.get("supplier_image", "")).strip().lower()
        if img and img not in ("nan", "none", "null", ""):
            image_url = hotel["supplier_image"]
        else:
            image_url = _hotel_image(hotel["name"], city)
        result.append({
            "supplier_id":        hotel["supplier_id"],
            "name":               hotel["name"],
            "rating_label":       hotel["rating_label"],
            "image_url":          image_url,
            "website":            hotel["website"],
            "meal_plan_name":     hotel.get("meal_plan_name", ""),
            "room_category_name": hotel.get("room_category_name", ""),
            "currency_code":      hotel.get("currency_code", ""),
            "rate_type":          hotel.get("rate_type", ""),
            "services":           hotel.get("services", []),
        })
    return result


# ─────────────────────────────────────────────────────────────────
# STEP 2 reminder – after  app = Flask(__name__)  add:
#
#   from regenerate import regenerate_bp
#   app.register_blueprint(regenerate_bp)
#
# That registers GET /api/regenerate_days and fixes the 404.
# ─────────────────────────────────────────────────────────────────