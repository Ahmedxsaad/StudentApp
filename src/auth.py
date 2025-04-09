# auth.py

import bcrypt
import os
from datetime import datetime, timezone
from api_client import APIClient

api = APIClient()

COOLDOWN_MINUTES = [5, 15, 30, 60, 120, 240, 480, 960, 1440, 28800, 43200, 57600, 86400, 100800, 100000000]

SECTION_ID_MAP = {
    "rt": 1,
    "gl": 2,
    "iia": 3,
    "imi": 4,
    "mpi": 5,
    "cba": 6,
    "bio": 7,
    "ch": 8
}

def get_cooldown_duration(step: int) -> int:
    """
    Return how many minutes to lock the user based on cooldown step.
    """
    if step < 1:
        return 0
    if step > len(COOLDOWN_MINUTES):
        return COOLDOWN_MINUTES[-1]
    return COOLDOWN_MINUTES[step - 1]

def is_verification_locked(user) -> tuple[bool, str]:
    """
    Check if a user is locked from verifying by looking at verification_locked_until.
    """
    if user.get('verification_locked_until'):
        locked_until = datetime.fromisoformat(user['verification_locked_until'])
        if datetime.now(timezone.utc) < locked_until:
            wait_until = locked_until.strftime("%Y-%m-%d %H:%M:%S UTC")
            return True, f"Locked until {wait_until}"
    return False, ""

def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(plain_password: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed.encode('utf-8'))

def clean_email(raw_email: str) -> str:
    """
    Sanitize email by allowing only letters, digits, @, dot, dash, underscore.
    Force lowercase and strip whitespace.
    """
    import re
    return re.sub(r'[^a-z0-9@._-]', '', raw_email.lower().strip())

# -------------------- API-BASED FUNCTIONS --------------------

def register_user(email, password, national_id, role='student'):
    email = clean_email(email)
    if not email.endswith("@insat.ucar.tn"):
        return False, "Only @insat.ucar.tn emails are allowed."

    data = api.register(email, password, national_id, role)
    return data.get("success", False), data.get("message", "")

def verify_user(email, token):
    email = clean_email(email)
    data = api.verify_user(email, token)
    return data.get("success", False), data.get("message", "")

def login_user(email, password):
    email = clean_email(email)
    data = api.login(email, password)
    if data.get("success"):
        user_info = data.get("user", {})
        refresh_token = data.get("refresh_token", "")
        auth_token = data.get("auth_token", "")
        return True, user_info, auth_token, refresh_token
    else:
        return False, data.get("message", ""), None, None

# Remember-me token
def generate_auth_token(user: dict) -> str:
    raw_token = os.urandom(32).hex()
    hashed_token = bcrypt.hashpw(raw_token.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    data = api.update_auth_token_in_db(user["id"], hashed_token)
    return raw_token if data.get("success") else ""

def login_user_with_token(token: str):
    data = api.login_with_token(token)
    if data.get("success"):
        return True, data.get("user")
    return False, data.get("message", "Invalid or expired token.")

def refresh_auth_token(user_id, refresh_token):
    data = api.refresh_auth_token(user_id, refresh_token)
    if data.get("success"):
        return True, data.get("auth_token")
    return False, data.get("message", "Refresh token failed")

def clear_auth_token(user: dict):
    api.clear_auth_token(user["id"])

def start_password_reset(email):
    email = clean_email(email)
    data = api.start_password_reset(email)
    return data.get("success", False), data.get("message", "")

def reset_password(token, new_password):
    data = api.reset_password(token, new_password)
    return data.get("success", False), data.get("message", "")

def unsubscribe_user(token):
    data = api.unsubscribe_user(token)
    return data.get("success", False), data.get("message", "")

def send_notification_to_all(title, body, admin_token):
    data = api.send_notification_to_all(title, body, admin_token)
    return data.get("success", False), data.get("message", "")

def send_notification_to_user(user_id, title, body, admin_token):
    data = api.send_notification_to_user(user_id, title, body, admin_token)
    return data.get("success", False), data.get("message", "")

def send_notification_to_section(section, title, body, admin_token):
    data = api.send_notification_to_section(section, title, body, admin_token)
    return data.get("success", False), data.get("message", "")

def mark_notification_as_read(notification_id, user_id):
    data = api.mark_notification_as_read(notification_id, user_id)
    return data.get("success", False), data.get("message", "")

def mark_notification_as_seen(notification_id, user_id):
    data = api.mark_notification_as_seen(notification_id, user_id)
    return data.get("success", False), data.get("message", "")

def resend_verification_code(email):
    data = api.resend_verification_code(email)
    return data.get("success", False), data.get("message", "")
