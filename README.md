# berth-status

External uptime check for Berth. It runs on GitHub Actions every 10 minutes, so it keeps working when Mike's Mac is asleep or the VM is gone. The repo is public, so Actions minutes are free and do not count against private repo builds.

## What it checks

- `api`: `https://api.atberth.com/v1/health` returns 200. If it does not, `https://api.atberth.com/overview` with no token must return 401, which proves Caddy and Conduit are answering.
- `site`: `https://atberth.com` returns 200.
- `tls`: the certificate for `api.atberth.com` has more than 14 days left.

Each check is tried 3 times, 20 seconds apart, before it counts as down.

## Alerts

Email goes to mikeshobes718@gmail.com through Resend from `alerts@reviewsandmarketing.com`, using the `RESEND_API_KEY` Actions secret. It emails only when the set of failing checks changes: one `[Berth] DOWN` email, then one `[Berth] recovered` email. The last state lives in `status.json` on the `state` branch.

Logs are public. The script prints only check names, status codes, and pass or fail. It never prints bodies, addresses, or secrets.

## Keep-alive

GitHub disables scheduled workflows after 60 days without repo activity. Once a month the workflow commits `heartbeat.txt` to the `state` branch and calls the enable workflow API, so the schedule stays on.

## Manual runs

```
gh workflow run uptime.yml -R mikeshobes718/berth-status
gh workflow run uptime.yml -R mikeshobes718/berth-status -f test_alert=true
```

The second one skips the checks and sends one `[Berth test]` email.

## Related

The Mac monitor (`com.berth.monitor`) and the VM watchdog do deeper checks. See the runbook in `berth-host`.
