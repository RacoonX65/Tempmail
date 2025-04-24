import random
import string
import requests
import time

def generate_random_string(length=10):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def create_temp_email():
    base = 'https://api.mail.tm'
    domain_data = requests.get(f"{base}/domains").json()
    domain = domain_data["hydra:member"][0]["domain"]

    email = f"{generate_random_string()}@{domain}"
    password = generate_random_string(12)

    res = requests.post(f"{base}/accounts", json={"address": email, "password": password})
    if res.status_code != 201:
        return None, None, None, res.text

    token_res = requests.post(f"{base}/token", json={"address": email, "password": password})
    token = token_res.json().get("token")
    return email, token, base, None

def poll_inbox(base, token, callback):
    headers = {"Authorization": f"Bearer {token}"}
    for _ in range(12):
        res = requests.get(f"{base}/messages", headers=headers)
        messages = res.json().get("hydra:member", [])
        if messages:
            for msg in messages:
                msg_id = msg['id']
                msg_detail = requests.get(f"{base}/messages/{msg_id}", headers=headers).json()
                subject = msg_detail['subject']
                body = msg_detail['text'][:500]
                callback(f"\n📬 {subject}\n\n{body}\n{'-'*40}\n")
            break
        time.sleep(10)
    else:
        callback("❌ No messages received in 2 minutes.")
