import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from models import DeviceAlertState, HazardZone
from i18n_service import render_message

logger = logging.getLogger(__name__)

def process_alert_deduplication(
    db: Session,
    device_id: str,
    active_hazardous_zones: List[Dict[str, Any]],
    lang: str = "en",
    now_utc: Optional[datetime] = None
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    ALERT DEDUPLICATION RULE:
    - Store (device_id, zone_id, severity) of alerts already sent.
    - Send a new alert only when a device enters a new zone or severity increases for that zone.
    - Reset when the zone expires or the user leaves it.
    - Include an "all clear" message when the user leaves danger.
    
    Returns (new_alerts_to_send, all_clear_alert_if_any).
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    # Fetch currently active alert states for this device
    existing_states = db.query(DeviceAlertState).filter(
        DeviceAlertState.device_id == device_id,
        DeviceAlertState.is_active == True
    ).all()
    
    existing_by_zone = {s.zone_id: s for s in existing_states}
    current_zone_ids = {z["id"] for z in active_hazardous_zones}

    new_alerts = []
    
    # Check current active zones for new entry or severity upgrade
    for zone in active_hazardous_zones:
        z_id = zone["id"]
        sev = zone["severity"]
        
        should_alert = False
        if z_id not in existing_by_zone:
            # Entered a new zone!
            new_state = DeviceAlertState(
                device_id=device_id,
                zone_id=z_id,
                severity=sev,
                last_alerted_at=now_utc,
                is_active=True
            )
            db.add(new_state)
            should_alert = True
        else:
            state_rec = existing_by_zone[z_id]
            if sev > state_rec.severity:
                # Severity increased!
                state_rec.severity = sev
                state_rec.last_alerted_at = now_utc
                should_alert = True

        if should_alert:
            action_msg = "Proceed to the nearest shelter immediately." if sev >= 3 else "Stay alert and monitor conditions."
            rendered = render_message("danger_here" if sev >= 3 else "caution_here", {
                "hazard": zone["type"],
                "distance": zone.get("distance_km", 0),
                "action": action_msg
            }, lang=lang)
            
            new_alerts.append({
                "zone_id": z_id,
                "type": zone["type"],
                "severity": sev,
                "title": f"{zone['type']} Alert",
                "message": rendered,
                "source": zone.get("source", "Official"),
                "timestamp": now_utc.isoformat()
            })

    # Check for zones user has exited (or expired)
    all_clear_alert = None
    had_danger_previously = any(s.severity >= 3 for s in existing_states)
    has_danger_now = any(z["severity"] >= 3 for z in active_hazardous_zones)

    for z_id, state_rec in existing_by_zone.items():
        if z_id not in current_zone_ids:
            # User left the zone or zone expired: reset state
            state_rec.is_active = False

    if had_danger_previously and not has_danger_now:
        # User left all danger zones -> trigger ALL CLEAR
        all_clear_msg = render_message("all_clear", {}, lang=lang)
        all_clear_alert = {
            "type": "ALL_CLEAR",
            "severity": 1,
            "title": "All Clear",
            "message": all_clear_msg,
            "timestamp": now_utc.isoformat()
        }

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error persisting alert states: {e}")

    return new_alerts, all_clear_alert
