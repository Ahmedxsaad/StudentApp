# email_utils.py

import requests
import threading

def send_email(to, subject, body, bearer_token=None):
    base_url = "put your_base_url_here"  # Replace with your actual base URL
    endpoint = f"{base_url}/api/send-email"

    headers = {}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    payload = {
        "to_email": to,
        "subject": subject,
        "body": body
    }
    r = requests.post(endpoint, json=payload, headers=headers, timeout=10)
    if not r.ok:
        raise Exception(f"Failed to send email: {r.status_code} {r.reason} => {r.text}")

