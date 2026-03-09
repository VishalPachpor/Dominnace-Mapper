import requests
import time

s = requests.Session()
# 1. Register
s.post("http://localhost/auth/register", json={"email": "fxuser2@test.com", "password": "password123"})

# 2. Login
resp = s.post("http://localhost/auth/login", json={"email": "fxuser2@test.com", "password": "password123"})
if resp.status_code == 200:
    token = resp.json()["access_token"]
    s.headers.update({"Authorization": f"Bearer {token}"})
    print("Logged in successfully.")
else:
    print("Login failed:", resp.text)
    exit(1)

# 3. Save MT5 Account
resp = s.post("http://localhost/users/meta-account", json={"meta_account_id": "mt5-test-999"})
print("Save MT5 Account:", resp.text)

# 4. Trigger Webhook
webhook_data = {
    "secret": "superwebhooksecret",
    "symbol": "XAUUSD",
    "side": "BUY",
    "price": "2345.50"
}
resp = s.post("http://localhost/api/webhook", json=webhook_data)
print("Webhook response:", resp.text)
