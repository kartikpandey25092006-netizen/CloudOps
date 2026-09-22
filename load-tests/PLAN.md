# CloudOps Load Testing Plan

## Overview

A phased load-testing plan to validate the self-healing capabilities of your AWS CloudOps infrastructure. This plan tests your EC2 instance (t3.micro running Nginx), CloudWatch alarms (75% CPU threshold), Lambda remediation, and the full recovery pipeline.

---

## Environment

| Parameter | Value |
|---|---|
| **Target** | EC2 `t3.micro` (`i-04e616740255f0eb1`) at `98.91.176.47` |
| **Application** | Nginx serving static React frontend |
| **Self-Healing Trigger** | CloudWatch alarm at CPU > 75% for 5 min |
| **Recovery Action** | Lambda → SSM → `systemctl restart nginx` |
| **Monitoring** | CloudWatch metrics + React CloudOps Dashboard |
| **Load Generator** | Your local Mac (via scripts in this directory) |

---

## Tools Used

| Tool | Why |
|---|---|
| **k6** (Grafana) | Modern, scriptable, low-overhead. Outputs percentile latencies natively. Single binary, no JVM. |
| **stress-ng** (on-server) | Direct CPU/memory pressure — bypasses network efficiency of Nginx for static files. |
| **Custom Bash scripts** | Quick validation and smoke tests. |
| **CloudWatch CLI** | Real-time alarm state monitoring from terminal. |

---

## Metrics We Measure

| Metric | Source | Why |
|---|---|---|
| **Response latency** (p50, p95, p99) | k6 | Detect degradation under load |
| **Error rate** (% of non-2xx) | k6 | Detect when Nginx starts dropping |
| **Requests/sec throughput** | k6 | Baseline capacity |
| **CPU Utilization** | CloudWatch | Verify alarm threshold crossing |
| **Memory Utilization** | SSM (custom) | Detect OOM conditions |
| **Alarm State transitions** | CloudWatch API | Confirm self-healing triggers |
| **Lambda invocations** | CloudWatch Logs | Confirm remediation fires |
| **Recovery time** | Audit logs (DynamoDB/S3) | Measure MTTR |

---

## Three-Phase Plan

### Phase 1: Pilot Test (Baseline)
**Goal**: Establish normal performance baseline.
- 10 virtual users, 2 minutes
- Measure baseline latency and throughput
- Confirm instance stays healthy

### Phase 2: Scaling Test (Ramp)
**Goal**: Find the breaking point where CPU crosses 75%.
- Ramp from 10 → 500 virtual users over 5 minutes
- Hold at peak for 5 minutes
- Monitor CloudWatch alarm state

### Phase 3: Stress Test (Self-Healing Validation)
**Goal**: Trigger the full self-healing pipeline and measure recovery.
- Use `stress-ng` on-server to guarantee CPU > 95%
- Simultaneously flood with HTTP traffic
- Verify: Alarm fires → Lambda triggers → Nginx restarts → Health recovers
- Measure total recovery time (MTTR)

---

## Constraints & Safety

> [!WARNING]
> - **t3.micro has CPU credits**. Sustained load will consume burst credits, then throttle to baseline (10% of a vCPU). This is by design for Free Tier.
> - **Do NOT run `while true; do curl & done`** — this forks thousands of processes on YOUR Mac and can freeze it.
> - All tests have explicit duration limits.
> - Cost impact: Negligible (within Free Tier).

---

## Deliverables

1. ✅ `load-tests/phase1-baseline.js` — k6 pilot test script
2. ✅ `load-tests/phase2-ramp.js` — k6 scaling test script  
3. ✅ `load-tests/phase3-stress.sh` — Full self-healing stress test
4. ✅ `load-tests/monitor.sh` — Real-time terminal monitoring dashboard
5. ✅ `load-tests/report.sh` — Post-test report generator
