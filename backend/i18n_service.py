import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Directory containing translation JSON templates
I18N_DIR = os.path.join(os.path.dirname(__file__), "i18n")

_TEMPLATES: Dict[str, Dict[str, str]] = {}

def load_templates():
    global _TEMPLATES
    if not os.path.exists(I18N_DIR):
        return
    for filename in os.listdir(I18N_DIR):
        if filename.endswith(".json"):
            lang = filename[:-5]
            try:
                with open(os.path.join(I18N_DIR, filename), "r", encoding="utf-8") as f:
                    _TEMPLATES[lang] = json.load(f)
            except Exception as e:
                logger.error(f"Error loading template {filename}: {e}")

def get_template(lang: str = "en") -> Dict[str, str]:
    if not _TEMPLATES:
        load_templates()
    return _TEMPLATES.get(lang, _TEMPLATES.get("en", {}))

def render_message(key: str, params: Dict[str, Any] = None, lang: str = "en") -> str:
    """Renders a localized message with parameter interpolation."""
    tpl_dict = get_template(lang)
    raw_text = tpl_dict.get(key)
    if not raw_text:
        # Fallback to English
        raw_text = get_template("en").get(key, key)
    
    if not params:
        return raw_text

    try:
        return raw_text.format(**params)
    except Exception:
        return raw_text
