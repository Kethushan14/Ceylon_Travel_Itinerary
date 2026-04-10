# ================================================================
# ADD THESE 3 ROUTES TO app.py  (replace your existing @app.route("/") POST block
# with itinerary_template1, and add template2 + template3 routes)
#
# Also add this helper function above the routes:
# ================================================================

def _render_itinerary(template_name):
    """Shared helper — loads itinerary from temp file / session and renders."""
    import tempfile
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
        "title": "Your Sri Lanka Journey",
        "days": days, "budget": budget, "budget_tier": budget_tier,
        "adults": adults, "children": children,
        "travel_style": travel_style, "meal_plan": meal_plan,
        "total_cities": len(unique_cities), "total_travelers": adults + children,
        "route_cities": route_cities, "route_display": " → ".join(route_cities),
        "hero_images": hero_images,
    }

    return render_template(
        template_name,
        header_data=header_data,
        itinerary_days=itinerary_days_stored,
        images=hero_images,
        days=days, budget=budget, budget_tier=budget_tier,
        adults=adults, children=children,
        travel_style=travel_style, meal_plan=meal_plan, schedule=schedule,
    )


# ── Template routes ──────────────────────────────────────────────
@app.route("/itinerary/classic")
def itinerary_template1():
    return _render_itinerary("itinerary.html")

@app.route("/itinerary/magazine")
def itinerary_template2():
    return _render_itinerary("itinerary2.html")

@app.route("/itinerary/timeline")
def itinerary_template3():
    return _render_itinerary("itinerary3.html")