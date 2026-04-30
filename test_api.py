from fastapi.testclient import TestClient
from bro import app
import string
import random

client = TestClient(app)
random_user = "user" + "".join(random.choices(string.ascii_lowercase, k=5))

print("Testing Registration...")
res = client.post("/register", json={"username": random_user, "password": "password123"})
print("Register:", res.status_code, res.json())

print("Testing Login...")
res2 = client.post("/login", json={"username": random_user, "password": "password123"})
print("Login:", res2.status_code, res2.json())
