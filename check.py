#!/usr/bin/env python3
"""External uptime check for Berth, run by GitHub Actions.

Logs are public, so this prints only check names, status codes, and pass/fail.
It never prints response bodies, addresses, or secrets.
"""
import datetime
import json
import os
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request

API = "https://api.atberth.com"
SITE = "https://atberth.com"
TLS_HOST = "api.atberth.com"
TLS_MIN_DAYS = 14
TRIES = 3
WAIT = 20
TO = "mikeshobes718@gmail.com"
FROM = "Berth Monitor <alerts@reviewsandmarketing.com>"
UA = "berth-status"


def status(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status
    except urllib.error.HTTPError as err:
        return err.code
    except Exception as err:
        return type(err).__name__


def check_api():
    code = status(API + "/v1/health")
    if code == 200:
        return True, "/v1/health 200"
    fallback = status(API + "/overview")
    return fallback == 401, "/v1/health %s, /overview %s (want 401)" % (code, fallback)


def check_site():
    code = status(SITE)
    return code == 200, "%s (want 200)" % code


def check_tls():
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((TLS_HOST, 443), timeout=20) as sock:
            with ctx.wrap_socket(sock, server_hostname=TLS_HOST) as tls:
                cert = tls.getpeercert()
        expires = datetime.datetime.fromtimestamp(ssl.cert_time_to_seconds(cert["notAfter"]), datetime.timezone.utc)
        days = (expires - datetime.datetime.now(datetime.timezone.utc)).days
        return days > TLS_MIN_DAYS, "%d days left (want > %d)" % (days, TLS_MIN_DAYS)
    except Exception as err:
        return False, type(err).__name__


CHECKS = [("api", check_api), ("site", check_site), ("tls", check_tls)]


def run(name, fn):
    for attempt in range(1, TRIES + 1):
        ok, detail = fn()
        print("%s attempt %d: %s %s" % (name, attempt, "pass" if ok else "fail", detail))
        if ok:
            return True, detail
        if attempt < TRIES:
            time.sleep(WAIT)
    return False, detail


def send(subject, body):
    key = os.environ.get("RESEND_API_KEY", "").strip()
    if not key:
        print("email: RESEND_API_KEY missing")
        return None
    payload = json.dumps({"from": FROM, "to": [TO], "subject": subject, "text": body}).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": UA},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            code = resp.status
    except urllib.error.HTTPError as err:
        code = err.code
    except Exception as err:
        code = type(err).__name__
    print("email: resend status %s" % code)
    return code


def load(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def main():
    state_dir = sys.argv[1] if len(sys.argv) > 1 else "state"
    run_url = os.environ.get("RUN_URL", "")

    if os.environ.get("TEST_ALERT") == "true":
        code = send("[Berth test] GitHub uptime test alert",
                    "Test email from the berth-status GitHub Actions uptime check. No action needed.\n" + run_url)
        return 0 if code == 200 else 1

    results = {name: run(name, fn) for name, fn in CHECKS}
    down = sorted(name for name, (ok, _) in results.items() if not ok)
    report = "\n".join("%s: %s, %s" % (n, "pass" if ok else "FAIL", d) for n, (ok, d) in results.items())

    path = os.path.join(state_dir, "status.json")
    prev = load(path)
    was_down = prev.get("down", [])
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")

    if down != was_down:
        if down:
            send("[Berth] DOWN: " + ", ".join(down), "External check from GitHub Actions failed.\n\n" + report + "\n\n" + run_url)
        else:
            send("[Berth] recovered", "All external checks pass again.\n\n" + report + "\n\n" + run_url)
        with open(path, "w") as fh:
            json.dump({"down": down, "since": now}, fh)
            fh.write("\n")
    else:
        print("state unchanged: %s" % (", ".join(down) if down else "all up"))

    month = now[:7]
    beat = os.path.join(state_dir, "heartbeat.txt")
    try:
        with open(beat) as fh:
            last = fh.read().strip()[:7]
    except OSError:
        last = ""
    if last != month:
        with open(beat, "w") as fh:
            fh.write(now + "\n")
        print("heartbeat: new month")
        with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as fh:
            fh.write("heartbeat=true\n")

    print("result: %s" % ("DOWN " + ", ".join(down) if down else "all up"))
    return 1 if down else 0


if __name__ == "__main__":
    sys.exit(main())
