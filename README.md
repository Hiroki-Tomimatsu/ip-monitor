# ip-monitor

**A tiny, single-file, dependency-free CLI that logs the host's current global IPv4 address once per run — intended to be driven by cron.**

`ip_monitor.py` queries two independent public IP-echo services (`ifconfig.io` and `ipconfig.io`), compares their answers, and prints a single timestamped log line with a status code. No daemon, no state file, no third-party packages — the whole script is ~60 lines of stdlib Python. Redirect stdout to a file from cron and you have a searchable history of your egress IP.

---

## Why this exists

Most ways to track a WAN IP over time involve either a heavyweight monitoring agent or a brittle one-liner like `curl ifconfig.io >> log`. The one-liner has three problems: it has no timestamp, it can't tell a network failure apart from a real IP change, and it silently trusts a single upstream service. `ip_monitor.py` fixes those three issues and nothing else — minimum viable IP history, wrapped in a format you can `grep` and `awk` for years.

---

## Features

- **Two-service cross-check.** Queries `ifconfig.io` and `ipconfig.io` independently and emits a `status` field that tells you whether the two sources agreed, disagreed, or failed.
- **One line per run.** Timestamp, per-service result, and status on a single line — cron-friendly and `grep`-friendly.
- **10-second timeout per service.** A hung service can't stall the run indefinitely.
- **`curl/8.0` User-Agent.** Avoids the default `Python-urllib/*` UA that some IP-echo services rate-limit or reject.
- **Fail-soft.** Network errors, HTTP errors, and decode errors are all caught per service and reported as `(unreachable)` rather than causing a crash. The script always exits `0` after writing exactly one log line.
- **Zero dependencies.** Python 3.9+ standard library only (`urllib`, `datetime`).

---

## Installation

```bash
git clone https://github.com/Hiroki-Tomimatsu/ip-monitor.git
cd ip-monitor
```

Python 3.9 or newer is recommended.

---

## Usage

### One-shot

```bash
python3 ip_monitor.py
```

Prints a single log line to stdout and exits.

### Hourly cron

```cron
0 * * * * /usr/bin/python3 /opt/ip-monitor/ip_monitor.py >> /var/log/ip-monitor.log 2>&1
```

### Every 5 minutes (finer-grained change detection)

```cron
*/5 * * * * /usr/bin/python3 /opt/ip-monitor/ip_monitor.py >> /var/log/ip-monitor.log 2>&1
```

### systemd timer alternative

`ip-monitor.service`:

```ini
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /opt/ip-monitor/ip_monitor.py
StandardOutput=append:/var/log/ip-monitor.log
StandardError=append:/var/log/ip-monitor.log
```

`ip-monitor.timer`:

```ini
[Timer]
OnCalendar=hourly
Persistent=true

[Install]
WantedBy=timers.target
```

---

## Log format

Each run appends one line in the following shape:

```
[YYYY-MM-DD HH:MM:SS] ifconfig.io=<result> ipconfig.io=<result> status=<STATUS>
```

Example entries:

```
[2026-04-21 09:00:00] ifconfig.io=203.0.113.42 ipconfig.io=203.0.113.42 status=MATCH
[2026-04-21 10:00:00] ifconfig.io=203.0.113.99 ipconfig.io=203.0.113.99 status=MATCH
[2026-04-21 11:00:00] ifconfig.io=203.0.113.99 ipconfig.io=(unreachable) status=PARTIAL
[2026-04-21 12:00:00] ifconfig.io=(unreachable) ipconfig.io=(unreachable) status=BOTH_FAILED
[2026-04-21 13:00:00] ifconfig.io=203.0.113.99 ipconfig.io=198.51.100.7 status=MISMATCH
```

### Status values

| Status | Meaning | Typical cause |
|--------|---------|---------------|
| `MATCH` | Both services returned the same IP. | Normal steady state. |
| `MISMATCH` | Both services succeeded but returned different IPs. | Dual-stack / multi-WAN edge, CDN mis-geolocation, or one of the services is misbehaving. Worth investigating but not usually an outage. |
| `PARTIAL` | Exactly one service answered. | Transient failure at one endpoint. Treat the answer as authoritative for this run. |
| `BOTH_FAILED` | Neither service answered. | Local internet down, local DNS broken, or a corporate proxy is blocking both hostnames. |

Because the output is structured and stable, grepping for events is trivial:

```bash
# Every IP change in the log
awk -F'[ =]' '{print $1,$2,$4}' /var/log/ip-monitor.log | uniq -f1

# Only failure-ish lines
grep -E 'status=(PARTIAL|BOTH_FAILED|MISMATCH)' /var/log/ip-monitor.log
```

---

## Configuration

The script is intentionally unconfigurable from the command line — tweaks are made by editing the module-level constants at the top of `ip_monitor.py`:

| Constant | Default | Purpose |
|----------|---------|---------|
| `TIMEOUT` | `10` | Per-service HTTP timeout in seconds. |
| `SERVICES` | `[("ifconfig.io", "https://ifconfig.io"), ("ipconfig.io", "https://ipconfig.io")]` | The `(name, URL)` pairs queried. Add a third provider here if you want a majority vote; the status logic extends naturally. |

---

## Use cases

**Home / SOHO dynamic-IP history.** Your ISP assigns a dynamic address. Set the cron job, and months later you have a searchable log of every reassignment, with timestamps, free.

**VPN / tunnel drop detection.** Run on the client side of a routed VPN. If the egress IP starts matching your ISP's address again, the tunnel dropped — the `grep` for the before/after IP will show exactly when.

**Lightweight availability probe.** `status=BOTH_FAILED` for N consecutive runs is a decent proxy for "local internet has been down for N hours" without any monitoring stack. Pipe the cron output through `logger` and alert on the pattern.

**Outbound-IP audit trail.** When you need to prove to a vendor, auditor, or IP-allowlisted API that your egress address at a specific time was X, the log line is the evidence.

---

## Implementation notes

- **Why two services and not three?** Two is enough to catch "the one service I'm relying on went down" — the most common failure mode — without turning a read-only monitoring script into something that hammers four different public APIs every run. If you want tie-breaking, add a third entry to `SERVICES`: the `determine_status` function uses `set(ips)` cardinality and works unchanged for N ≥ 2.
- **First-line decode.** The script reads the response and takes only the first line, so services that return a trailing newline (or occasionally a short HTML wrapper on error pages) don't pollute the log with multi-line output.
- **Exit status is always `0`.** Because the script is designed to be fed into an ever-growing log file from cron, a non-zero exit would just generate noise in mail spools. All failure modes are encoded in the `status=` field instead.

---

## License

MIT. See `LICENSE`.

---

## Acknowledgements

- [ifconfig.io](https://ifconfig.io/) and [ipconfig.io](https://ipconfig.io/) for providing free, reliable IP-echo endpoints that make tools like this possible.
