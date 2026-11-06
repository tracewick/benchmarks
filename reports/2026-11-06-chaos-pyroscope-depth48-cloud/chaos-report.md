# Report: chaos Pyroscope latency — 2026-11-06

| Field | Value |
| --- | --- |
| Host | Linux nsk-1-vm-tsr3 7.0.0-42-generic #42-Ubuntu SMP PREEMPT_DYNAMIC Thu Oct 15 08:06:44 UTC 2026 x86_64 GNU/Linux |
| repo SHA | `a5e2560cda67cf4ebbe2460726c18beccc4e8559` |
| Toxic | latency 3000ms on toxiproxy→pyroscope |
| RATE / duration | 20 / 60s |
| sampleRate | 1.0 |
| WORK_STACK_DEPTH | 48 |
| Peak spool files during toxic | 500 |
| Peak spool bytes | 1085178 (1.03 MiB) |
| HTTP fail rate | 0 |

App requests should remain healthy while delivery slows and spool grows.
