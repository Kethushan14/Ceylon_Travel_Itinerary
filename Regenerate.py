# regenerate.py  – mount this Blueprint in app.py with:
#   from regenerate import regenerate_bp
#   app.register_blueprint(regenerate_bp)

import os
import json
import logging
import tempfile

from flask import Blueprint, request, jsonify, session

logger = logging.getLogger(__name__)

regenerate_bp = Blueprint("regenerate_bp", __name__)


# ── helpers imported lazily to avoid circular imports ────────────────────────
def _imports():
    from app import (
        client,
        get_budget_tier,
        get_city_description,
        get_city_services,
        fetch_hotel_images,
    )
    return client, get_budget_tier, get_city_description, get_city_services, fetch_hotel_images


# ── Lookup maps ───────────────────────────────────────────────────────────────
MEAL_PLAN_MAP = {
    "1": "Room Only", "2": "Bed & Breakfast", "3": "Half Board",
    "4": "Full Board", "7": "All Inclusive", "9": "Room Only", "10": "Full Board",
}
ROOM_CATEGORY_MAP = {
    "1": "Standard", "2": "Deluxe", "6": "Superior", "7": "Executive",
    "8": "Executive Suite", "9": "Deluxe Suite", "10": "Luxury Suite",
    "11": "Colonial Room", "12": "Ocean View Room", "13": "Direct Ocean View",
    "22": "Suite", "26": "Penthouse", "27": "Family Suite", "28": "Junior Suite",
    "39": "Bungalow", "45": "Garden Room", "51": "Sea View Room", "52": "Royal Suite",
    "62": "Family Room", "63": "Honeymoon Suite", "72": "Studio", "78": "Cottage",
    "91": "Whole Villa", "111": "Presidential Suite", "127": "Dormitory",
    "163": "Deluxe Villa", "164": "Garden Villa", "165": "Family Bungalow",
    "180": "Loft", "199": "Camping Tent", "200": "Classic", "209": "Tree House",
    "257": "Luxury Tent", "267": "Deluxe Tent", "282": "Tent", "305": "Bedroom",
    "306": "Cabana", "307": "Villa",
}
CURRENCY_MAP  = {"0": "LKR", "1": "USD", "2": "USD", "3": "EUR", "5": "GBP", "8": "AUD", "9": "LKR"}
RATE_TYPE_MAP = {"1": "Fixed Rate", "2": "Per Person", "3": "Per Vehicle"}
RIDE_TYPE_MAP = {"0": "Standard", "1": "Jeep", "2": "Boat", "3": "Boat", "4": "Train"}
VEHICLE_CATEGORY_MAP = {
    "1": "Car", "3": "Van", "4": "Micro Van", "5": "33-Seater Coach",
    "6": "Large Coach", "7": "Baggage Van", "8": "Mini Coach",
    "9": "KDH High Roof Van", "10": "SUV",
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
    if s.lower() in ("nan", "none", "null", ""):
        return ""
    try:
        s = str(int(float(s)))
    except (ValueError, TypeError):
        return s
    return mapping.get(s, "")


# ── Prompt builder ────────────────────────────────────────────────────────────
def _build_enriched_prompt(day_num, cities, user_instruction,
                            days, budget, adults, children,
                            travel_style, budget_tier, meal_plan,
                            services_by_city, hotel_info,
                            get_city_description_fn):
    city_label = " → ".join(cities)
    pax        = f"{adults} adult(s)" + (f", {children} child(ren)" if children else "")
    bud_str    = f"USD {budget} total" if budget else "not specified"

    city_descs = ""
    for city in cities:
        try:
            desc = get_city_description_fn(city)
            if desc:
                city_descs += f"  {city}: {desc[:300]}\n"
        except Exception:
            pass

    svc_block = ""
    for city in cities:
        svcs = services_by_city.get(city, {})
        if svcs:
            svc_block += f"\n  {city}:\n"
            for cat, data in svcs.items():
                sups = ", ".join(data["suppliers"][:4]) if isinstance(data, dict) else str(data)
                svc_block += f"    [{cat}] → {sups}\n"

    hotel_meal_guidance = ""
    primary_hotel       = ""
    for city in cities:
        if city in hotel_info:
            h     = hotel_info[city]
            hname = h.get("name", "")
            hmeal = h.get("meal_plan_name", "")
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


def _fallback_plan(cities, budget_tier, meal_plan, hotel_info):
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


# ── Route ─────────────────────────────────────────────────────────────────────
@regenerate_bp.route("/api/regenerate_days", methods=["POST"])
def regenerate_days():
    try:
        client, get_budget_tier, get_city_description, get_city_services, fetch_hotel_images = _imports()
    except Exception as e:
        logger.error(f"Import error in regenerate_days: {e}")
        return jsonify({"status": 500, "message": f"Server configuration error: {e}"}), 500

    try:
        # ── Parse body ────────────────────────────────────────────────────
        body = request.get_json(force=True, silent=True)
        if not body:
            return jsonify({"status": 400, "message": "No JSON body provided"}), 400

        selected_days = [int(d) for d in body.get("selected_days", [])]
        user_prompt   = str(body.get("user_prompt", "")).strip()
        itinerary_id  = str(body.get("itinerary_id", "")).strip()

        logger.info(f"regenerate_days: days={selected_days}, id={itinerary_id!r}, prompt={user_prompt!r}")

        if not selected_days:
            return jsonify({"status": 400, "message": "No days selected"}), 400
        if not user_prompt:
            return jsonify({"status": 400, "message": "No modification prompt provided"}), 400

        # ── Load itinerary ─────────────────────────────────────────────────
        data = None
        itinerary_days_stored = None

        if itinerary_id:
            itinerary_file = os.path.join(tempfile.gettempdir(), f"itinerary_{itinerary_id}.json")
            if os.path.exists(itinerary_file):
                try:
                    with open(itinerary_file, "r", encoding="utf-8") as f:
                        full_data = json.load(f)
                    data = full_data
                    itinerary_days_stored = full_data.get("itinerary_days", [])
                    logger.info(f"Loaded itinerary from file: {itinerary_file}")
                except Exception as e:
                    logger.warning(f"Could not read itinerary file: {e}")

        if data is None:
            data = session.get("itinerary_data")
            if data:
                logger.info("Loaded itinerary from session")
            else:
                return jsonify({
                    "status": 404,
                    "message": "Itinerary data not found. Please generate the itinerary again.",
                }), 404

        # ── Extract fields ─────────────────────────────────────────────────
        days         = int(data.get("days", 7))
        budget       = data.get("budget")
        adults       = int(data.get("adults", 1))
        children     = int(data.get("children", 0))
        travel_style = str(data.get("travel_style", "General Sightseeing"))
        meal_plan    = str(data.get("meal_plan", "Breakfast and Dinner"))
        schedule     = data.get("schedule", [])

        if not schedule:
            return jsonify({"status": 400, "message": "Itinerary schedule is empty."}), 400

        budget_tier = get_budget_tier(budget, days, adults, children)

        # ── Regenerate selected days ───────────────────────────────────────
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

            try:
                enriched_prompt = _build_enriched_prompt(
                    day_num=day_num,
                    cities=cities,
                    user_instruction=user_prompt,
                    days=days,
                    budget=budget,
                    adults=adults,
                    children=children,
                    travel_style=travel_style,
                    budget_tier=budget_tier,
                    meal_plan=meal_plan,
                    services_by_city=services_by_city,
                    hotel_info=hotel_info,
                    get_city_description_fn=get_city_description,
                )

                resp = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a precise Sri Lanka travel planner. "
                                "Modify the itinerary day based on the user's request. "
                                "Follow the format exactly. Always name the hotel for lunch and dinner."
                            ),
                        },
                        {"role": "user", "content": enriched_prompt},
                    ],
                    temperature=0.6,
                    max_tokens=1200,
                )
                new_ai_plan = resp.choices[0].message.content.strip()
                logger.info(f"LLM returned plan for day {day_num} ({len(new_ai_plan)} chars)")

            except Exception as e:
                logger.error(f"LLM error for day {day_num}: {e}")
                new_ai_plan = _fallback_plan(cities, budget_tier, meal_plan, hotel_info)

            # Hotel images for response
            hotel_images_out = {}
            for city in cities:
                try:
                    hotels = fetch_hotel_images(city, tier=budget_tier["tier"], max_hotels=1)
                    hotel_images_out[city] = hotels
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

            # Persist into stored days
            if itinerary_days_stored:
                for stored_day in itinerary_days_stored:
                    if int(stored_day.get("day_num", -1)) == day_num:
                        stored_day["ai_plan"]      = new_ai_plan
                        stored_day["hotel_images"] = hotel_images_out
                        break

        if not updated_days:
            return jsonify({"status": 400, "message": "No valid days were regenerated."}), 400

        # ── Persist back to temp file ──────────────────────────────────────
        if itinerary_id and itinerary_days_stored:
            try:
                itinerary_file = os.path.join(tempfile.gettempdir(), f"itinerary_{itinerary_id}.json")
                if os.path.exists(itinerary_file):
                    with open(itinerary_file, "r", encoding="utf-8") as f:
                        saved = json.load(f)
                    saved["itinerary_days"] = itinerary_days_stored
                    with open(itinerary_file, "w", encoding="utf-8") as f:
                        json.dump(saved, f, ensure_ascii=False)
                    logger.info(f"Updated itinerary file id={itinerary_id}")
            except Exception as e:
                logger.warning(f"Could not update itinerary file: {e}")

        return jsonify({
            "status":       200,
            "message":      f"Successfully regenerated {len(updated_days)} day(s).",
            "updated_days": updated_days,
        })

    except Exception as e:
        logger.error(f"regenerate_days UNHANDLED ERROR: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"status": 500, "message": f"Server error: {str(e)}"}), 500