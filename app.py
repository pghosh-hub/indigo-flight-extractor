def parse_block_style(text: str) -> List[Dict]:
    """
    Improved multi-flight parser.
    Detects multiple 6E flights in a single screenshot and extracts each one individually.
    """
    flights = re.split(r'(?=\b6E\s?\d{1,4}\b)', text)
    rows = []

    for blk in flights:
        if not re.search(r'\b6E\s?\d{1,4}\b', blk):
            continue

        mfn = re.search(r'\b6E\s?\d{1,4}\b(?:\.\s*[A-Za-z0-9]+)?', blk, re.I)
        flight_no = mfn.group(0).strip() if mfn else ""

        # Extract times (e.g. 16:55 or 03:40)
        times = re.findall(r'([01]?\d|2[0-3]):[0-5]\d', blk)
        dep = times[0] if len(times) >= 1 else ""
        arr = times[1] if len(times) >= 2 else ""

        # Find cities (e.g. Raipur, Kolkata, Hanoi)
        cities = re.findall(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b', blk)
        city_from = cities[0] if len(cities) > 0 else ""
        city_to = cities[1] if len(cities) > 1 else ""

        # Duration (01h 25m)
        mdur = re.search(r'(\d{1,2}h\s?\d{0,2}m?)', blk, re.I)
        duration = mdur.group(0) if mdur else ""

        # Layover
        mlay = re.search(r'(\d{1,2}h\s?\d{1,2}m.*?)layover', blk, re.I)
        layover = mlay.group(0).replace("layover", "").strip() if mlay else ""

        row = {
            "Carrier": "Indigo",
            "Flight No.": flight_no,
            "From": city_from.title(),
            "To": city_to.title(),
            "Departure": dep,
            "Arrival": arr,
            "Duration": duration,
            "Layover Time": layover
        }
        rows.append(row)

    return rows
