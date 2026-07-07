#!/usr/bin/env python3
"""Minimal worker dummy — connects to OpenCloud, polls for jobs, prints what it gets."""

import time
import requests

URL = "https://cloud.brandis.eu"
USER = "worker"
TOKEN_NAME = "worker2"
TOKEN = "routing humming modified prune unharmed pessimist"
PICK = ["md-to-pdf", "zip-create", "test-echo"]

session = requests.Session()
session.auth = (USER, TOKEN)
session.verify = True

print(f"{USER}/{TOKEN_NAME} connecting to {URL}")
print(f"pick: {PICK}")

while True:
    try:
        resp = session.post(f"{URL}/api/v0/jobs/workers/poll", json={
            "pick": PICK,
            "capacity": 1,
            "status": [],
        }, timeout=30)

        if resp.status_code == 200:
            data = resp.json()
            slots = data.get("slots") or {}
            denied = data.get("denied") or []
            assign = data.get("assign") or []
            cancel = data.get("cancel") or []

            if assign:
                print(f"  ASSIGNED: {[a['jobId'] for a in assign]}")
            if cancel:
                print(f"  CANCEL: {cancel}")
            if denied:
                print(f"  denied: {denied}")
            if slots:
                print(f"  slots: {slots}")
            if not assign and not denied:
                print("  idle")
        elif resp.status_code == 403:
            print(f"  403 — not allowed: {resp.json().get('denied', [])}")
        elif resp.status_code == 429:
            print("  429 — too fast")
        else:
            print(f"  HTTP {resp.status_code}: {resp.text[:100]}")

    except Exception as e:
        print(f"  error: {e}")

    time.sleep(5)
