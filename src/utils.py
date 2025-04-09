# utils.py
import logging
import os
from datetime import datetime

def generate_name_variations(name):
    variations = set()
    variations.add(name)
    replacements = [
        ('I', 'Y'),
        ('Y', 'I'),
        ('E', 'A'),
        ('A', 'E'),
        ('OU', 'U'),
        ('U', 'OU'),
        ('MOHAMED', 'MOHAMMED'),
        ('MOHAMMED', 'MOHAMED'),
        ('MARIEM', 'MERIEM'),
        ('MERIEM', 'MARIEM'),
        ('NOUR ELHOUDA', 'NOUR EL HOUDA'),
        ('HEDI', 'HEDI')
    ]
    parts = name.split()
    if len(parts) > 2:
        combined = ''.join(parts)
        variations.add(combined)
        variations.add(parts[0] + parts[-1])

    for old, new in replacements:
        if old in name:
            variations.add(name.replace(old, new))
        if new in name:
            variations.add(name.replace(new, old))

    name_no_space = name.replace(' ', '').replace('-', '')
    variations.add(name_no_space)

    return variations

if not os.path.exists('logs'):
    os.makedirs('logs')

logging.basicConfig(
    filename=f"logs/app_{datetime.now().strftime('%Y%m%d')}.log",
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
def log_admin_action(admin_email, message):
    log_line = f"[ADMIN={admin_email}] {message}"
    logging.info(log_line)
def log_action(action):
    logging.info(action)
