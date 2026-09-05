import os
import json
import httpx

gemini_key = os.environ.get("GEMINI_API_KEY", "AQ.Ab8RN6J-gYen3JM9XzX9bCUNnaAQLKBW_L6jvvwXyhXgdYeKUw")

prompt = """
You are a law enforcement data classification AI.
Classify this sample record into one of three canonical buckets: 'entity', 'transaction', or 'observation'.
Return ONLY a valid JSON array of items with this exact schema:
[
  {
    "bucket": "entity",
    "mapped_data": {
      "id": "drone_99",
      "type": "drone",
      "identifier": "DRONE-99",
      "display_name": "SkyHawk Surveillance Unit",
      "platform": "SurveillanceDrone",
      "location": "Sector 17, Chandigarh",
      "risk_score": 75,
      "metadata": {
        "altitude_m": 150.5,
        "freq_ghz": 2.4
      }
    }
  }
]

Input record: [{"drone_id": "DRONE-99", "pilot_alias": "SkyHawk", "altitude_m": 150.5, "freq_ghz": 2.4, "city": "Chandigarh"}]
"""

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
payload = {
    "contents": [{
        "parts": [{"text": prompt}]
    }],
    "generationConfig": {
        "responseMimeType": "application/json"
    }
}

print("Testing Gemini API call with gemini-2.5-flash...")
try:
    res = httpx.post(url, json=payload, timeout=20.0)
    print(f"Status Code: {res.status_code}")
    print("Response JSON:")
    print(res.text)
except Exception as e:
    print("API Error:", e)
