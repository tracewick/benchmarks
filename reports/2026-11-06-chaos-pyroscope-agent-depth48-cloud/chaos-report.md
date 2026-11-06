# Report: chaos Pyroscope latency — 2026-11-06

| Field | Value |
| --- | --- |
| Host | Linux nsk-1-vm-tsr3 7.0.0-42-generic #42-Ubuntu SMP PREEMPT_DYNAMIC Thu Oct 15 08:06:44 UTC 2026 x86_64 GNU/Linux |
| repo SHA | `e9c36a0fc007d73d5c5e392db328869350df5190` |
| Toxic | latency 3000ms on toxiproxy→pyroscope |
| RATE / duration | 20 / 60s |
| sampleRate | 1.0 |
| WORK_STACK_DEPTH | 48 |
| READER | agent |
| Peak spool files during toxic | 172 |
| Peak spool bytes | 535043 (0.51 MiB) |
| HTTP fail rate | 0 |

App requests should remain healthy while delivery slows and spool grows.
