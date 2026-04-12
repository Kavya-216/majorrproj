# Reconciliation Table (Frozen)

Freeze timestamp (UTC): 2026-04-12T00:00:00Z
Authority order used: user mandate > architecture docs > examples

| Parameter | Conflicting Values Found | Chosen Value | Why Chosen | Impacted Modules |
|---|---|---|---|---|
| Payload encryption mode | AES-256-CBC, AES-256-ECB | AES-256-CBC + HMAC-SHA256 integrity | User explicitly required rigor on JSON payload + encryption and no silent security fallback. CBC with random IV avoids deterministic block leakage from ECB. HMAC adds explicit integrity verification. | ARCH_6, ARCH_8 |
| Payload size target | Fixed 116 bytes, under 1000 bytes | Hard limit under 1000 bytes; engineering target 116 bytes where feasible | Both appear across docs. A hard pass/fail limit must be robust to metadata growth (seq/mac/version). 116 is retained as optimization target, not hard requirement. | ARCH_6, ARCH_8 |
| Confidence threshold | 0.5 global, 0.85+ class-specific | Class-specific thresholds with default 0.85 | Threat alerts need high precision. Class-specific thresholds reduce false positives while preserving compatibility with ARCH_5 confidence output. | ARCH_5, ARCH_6, ARCH_7 |
| Power model quiescent | Very low quiescent (~0.5mW), realistic 50mW | 50mW quiescent baseline | Multiple docs label ultra-low quiescent as unrealistic. 50mW is deployment-realistic for always-listening MCU + codec. | ARCH_7 |
| Battery capacity | 3000mAh, 5000mAh | 5000mAh default, 3000mAh included in sensitivity sweep | 5000mAh aligns with high-level architecture deployment goal. 3000mAh remains evaluated in sensitivity analysis to expose mission risk. | ARCH_7 |
| Inference timing model | Short-window streaming, 10-second window pipeline | 10ms frame-hop streaming interface with 1-second decision cadence and 10-second contextual window support | Preserves strict frame contracts from ARCH_1/2 while supporting friend’s ARCH_5 contract and low-latency operation. | ARCH_1, ARCH_2, ARCH_5, ARCH_6, ARCH_7 |
| LoRa TX assumptions | 14dBm/25mW, 20dBm/100mW | 20dBm/100mW default, 14dBm/25mW sensitivity mode | 20dBm provides conservative worst-case reliability. 14dBm retained for energy sensitivity studies and recommendations. | ARCH_7, ARCH_8 |

## Frozen Rules

1. No module can override this table implicitly.
2. Any override must be explicit and logged in artifacts.
3. Encryption/network failures are hard failures (no silent fallback).
4. All constants used in code must appear in canonical config.
