"""
A gazetteer of Indian places (all 28 state capitals + 8 union
territories, plus ~70 other major cities) with approximate lat/lon,
used to scan the Dread archive for real place-name mentions.

This is public geographic reference data (city coordinates), not
anything derived from either dataset. Coordinates are city-center
approximations, not precise addresses.

ALIASES maps common alternate/historical names (Bombay, Calcutta,
Bangalore, etc. — names that actually show up in casual forum text
more often than the official name) to the canonical name used as the
map marker label.
"""

from __future__ import annotations

# canonical_name -> (lat, lon)
PLACES: dict[str, tuple[float, float]] = {
    # State capitals
    "Amaravati": (16.5062, 80.6480),
    "Itanagar": (27.0844, 93.6053),
    "Guwahati": (26.1445, 91.7362),
    "Patna": (25.5941, 85.1376),
    "Raipur": (21.2514, 81.6296),
    "Panaji": (15.4909, 73.8278),
    "Gandhinagar": (23.2156, 72.6369),
    "Chandigarh": (30.7333, 76.7794),
    "Shimla": (31.1048, 77.1734),
    "Ranchi": (23.3441, 85.3096),
    "Bengaluru": (12.9716, 77.5946),
    "Thiruvananthapuram": (8.5241, 76.9366),
    "Bhopal": (23.2599, 77.4126),
    "Mumbai": (19.0760, 72.8777),
    "Imphal": (24.8170, 93.9368),
    "Shillong": (25.5788, 91.8933),
    "Aizawl": (23.7271, 92.7176),
    "Kohima": (25.6751, 94.1086),
    "Bhubaneswar": (20.2961, 85.8245),
    "Jaipur": (26.9124, 75.7873),
    "Gangtok": (27.3389, 88.6065),
    "Chennai": (13.0827, 80.2707),
    "Hyderabad": (17.3850, 78.4867),
    "Agartala": (23.8315, 91.2868),
    "Lucknow": (26.8467, 80.9462),
    "Dehradun": (30.3165, 78.0322),
    "Kolkata": (22.5726, 88.3639),
    # Union territories
    "New Delhi": (28.6139, 77.2090),
    "Srinagar": (34.0837, 74.7973),
    "Jammu": (32.7266, 74.8570),
    "Leh": (34.1526, 77.5771),
    "Puducherry": (11.9416, 79.8083),
    "Port Blair": (11.6234, 92.7265),
    "Kavaratti": (10.5593, 72.6358),
    "Daman": (20.3974, 72.8328),
    # Other major cities frequently referenced independent of their state capital
    "Ludhiana": (30.9010, 75.8573),
    "Amritsar": (31.6340, 74.8723),
    "Jalandhar": (31.3260, 75.5762),
    "Patiala": (30.3398, 76.3869),
    "Gurugram": (28.4595, 77.0266),
    "Faridabad": (28.4089, 77.3178),
    "Noida": (28.5355, 77.3910),
    "Ghaziabad": (28.6692, 77.4538),
    "Meerut": (28.9845, 77.7064),
    "Aligarh": (27.8974, 78.0880),
    "Kanpur": (26.4499, 80.3319),
    "Agra": (27.1767, 78.0081),
    "Varanasi": (25.3176, 82.9739),
    "Prayagraj": (25.4358, 81.8463),
    "Bareilly": (28.3670, 79.4304),
    "Moradabad": (28.8386, 78.7733),
    "Gorakhpur": (26.7606, 83.3732),
    "Pune": (18.5204, 73.8567),
    "Nagpur": (21.1458, 79.0882),
    "Nashik": (19.9975, 73.7898),
    "Navi Mumbai": (19.0330, 73.0297),
    "Aurangabad": (19.8762, 75.3433),
    "Solapur": (17.6599, 75.9064),
    "Kolhapur": (16.7050, 74.2433),
    "Ahmedabad": (23.0225, 72.5714),
    "Surat": (21.1702, 72.8311),
    "Vadodara": (22.3072, 73.1812),
    "Rajkot": (22.3039, 70.8022),
    "Bhavnagar": (21.7645, 72.1519),
    "Indore": (22.7196, 75.8577),
    "Jabalpur": (23.1815, 79.9864),
    "Gwalior": (26.2183, 78.1828),
    "Ujjain": (23.1793, 75.7849),
    "Jodhpur": (26.2389, 73.0243),
    "Udaipur": (24.5854, 73.7125),
    "Kota": (25.2138, 75.8648),
    "Ajmer": (26.4499, 74.6399),
    "Bikaner": (28.0229, 73.3119),
    "Coimbatore": (11.0168, 76.9558),
    "Madurai": (9.9252, 78.1198),
    "Tiruchirappalli": (10.7905, 78.7047),
    "Mysuru": (12.2958, 76.6394),
    "Mangaluru": (12.9141, 74.8560),
    "Hubballi": (15.3647, 75.1240),
    "Belagavi": (15.8497, 74.4977),
    "Kochi": (9.9312, 76.2673),
    "Kozhikode": (11.2588, 75.7804),
    "Thrissur": (10.5276, 76.2144),
    "Kollam": (8.8932, 76.6141),
    "Visakhapatnam": (17.6868, 83.2185),
    "Vijayawada": (16.5062, 80.6480),
    "Guntur": (16.3067, 80.4365),
    "Tirupati": (13.6288, 79.4192),
    "Warangal": (17.9689, 79.5941),
    "Nizamabad": (18.6725, 78.0941),
    "Jamshedpur": (22.8046, 86.2029),
    "Dhanbad": (23.7957, 86.4304),
    "Bokaro": (23.6693, 86.1511),
    "Siliguri": (26.7271, 88.3953),
    "Asansol": (23.6739, 86.9524),
    "Durgapur": (23.5204, 87.3119),
    "Howrah": (22.5958, 88.2636),
}

# lowercase_alias -> canonical name in PLACES
ALIASES: dict[str, str] = {
    "delhi": "New Delhi",
    "delhi ncr": "New Delhi",
    "ncr": "New Delhi",
    "bombay": "Mumbai",
    "calcutta": "Kolkata",
    "madras": "Chennai",
    "bangalore": "Bengaluru",
    "cochin": "Kochi",
    "poona": "Pune",
    "gurgaon": "Gurugram",
    "baroda": "Vadodara",
    "trivandrum": "Thiruvananthapuram",
    "mysore": "Mysuru",
    "allahabad": "Prayagraj",
    "pondicherry": "Puducherry",
    "vizag": "Visakhapatnam",
    "trichy": "Tiruchirappalli",
    "calicut": "Kozhikode",
}

# Deliberately NOT in the gazetteer, even though they're real Indian
# places, because they collide with common English words/names and
# produced confirmed false positives when tested against this archive's
# actual (multilingual, English-slang-heavy) text:
#   - "Salem" -> Salem, Oregon / Salem's Lot / Salem Witch Trials, zero
#     Tamil Nadu hits in a manual spot-check of every match
#   - "Thane" -> matched only as the Shakespearean title ("Thane of
#     Cawdor"), zero Maharashtra hits
# If you add more short/ambiguous names later (Leh, Kota, Goa, Una,
# etc.), spot-check real match context first — see the "false positive
# check" cells run during development, or just re-run extract with the
# new term and eyeball a few hits before trusting the count.
