import json
from typing import Dict, Any, List

# Emergency numbers per country
# India: 112 national emergency, 100 police, 101 fire, 102/108 ambulance, 1078 disaster management
# Plus US, UK, EU, Japan, Thailand, Indonesia, Sri Lanka, UAE, Australia
# Note: Emergency numbers must be verified before release.

EMERGENCY_NUMBERS: Dict[str, Dict[str, Any]] = {
    "IN": {
        "country": "India",
        "primary": "112",
        "police": "100",
        "fire": "101",
        "ambulance": "108",
        "disaster_management": "1078",
        "tourist_helpline": "1363",
        "women_helpline": "1091",
        "embassy_notes": "Call 112 for all unified emergency services across India."
    },
    "US": {
        "country": "United States",
        "primary": "911",
        "police": "911",
        "fire": "911",
        "ambulance": "911",
        "disaster_management": "FEMA (800) 621-3362",
        "tourist_helpline": "",
        "women_helpline": "",
        "embassy_notes": "Call 911 for all emergencies."
    },
    "GB": {
        "country": "United Kingdom",
        "primary": "999",
        "police": "999",
        "fire": "999",
        "ambulance": "999",
        "disaster_management": "111 (non-emergency)",
        "tourist_helpline": "",
        "women_helpline": "",
        "embassy_notes": "Call 999 or 112."
    },
    "EU": {
        "country": "European Union",
        "primary": "112",
        "police": "112",
        "fire": "112",
        "ambulance": "112",
        "disaster_management": "112",
        "tourist_helpline": "",
        "women_helpline": "",
        "embassy_notes": "112 works across all EU member states."
    },
    "JP": {
        "country": "Japan",
        "primary": "110",
        "police": "110",
        "fire": "119",
        "ambulance": "119",
        "disaster_management": "#7119",
        "tourist_helpline": "050-3816-2787",
        "women_helpline": "",
        "embassy_notes": "110 for police, 119 for fire and ambulance."
    },
    "TH": {
        "country": "Thailand",
        "primary": "191",
        "police": "191",
        "fire": "199",
        "ambulance": "1669",
        "disaster_management": "1784",
        "tourist_helpline": "1155",
        "women_helpline": "",
        "embassy_notes": "Tourist Police helpline is 1155 (English spoken)."
    },
    "ID": {
        "country": "Indonesia",
        "primary": "112",
        "police": "110",
        "fire": "113",
        "ambulance": "118",
        "disaster_management": "117",
        "tourist_helpline": "",
        "women_helpline": "",
        "embassy_notes": "112 is active in major cities including Bali and Jakarta."
    },
    "LK": {
        "country": "Sri Lanka",
        "primary": "119",
        "police": "119",
        "fire": "110",
        "ambulance": "1990",
        "disaster_management": "117",
        "tourist_helpline": "1912",
        "women_helpline": "",
        "embassy_notes": "Suwa Seriya ambulance service is 1990."
    },
    "AE": {
        "country": "United Arab Emirates",
        "primary": "999",
        "police": "999",
        "fire": "997",
        "ambulance": "998",
        "disaster_management": "999",
        "tourist_helpline": "8004438",
        "women_helpline": "",
        "embassy_notes": "999 for Police, 998 for Ambulance."
    },
    "AU": {
        "country": "Australia",
        "primary": "000",
        "police": "000",
        "fire": "000",
        "ambulance": "000",
        "disaster_management": "SES 132 500",
        "tourist_helpline": "",
        "women_helpline": "",
        "embassy_notes": "Triple Zero (000) for all primary emergencies."
    }
}

def get_emergency_numbers(country_code: str = "IN") -> Dict[str, Any]:
    code = (country_code or "IN").upper()
    return EMERGENCY_NUMBERS.get(code, EMERGENCY_NUMBERS["IN"])
