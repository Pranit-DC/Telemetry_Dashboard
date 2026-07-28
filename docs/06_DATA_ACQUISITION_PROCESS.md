# 6. Data Acquisition Pipeline — Firmware to Dashboard

This is the detailed, end-to-end path: how the Arduino GIGA R1 captures a decay pulse,
how it gets the result to the PC (two different ways), and how the dashboard turns that
into a `TraceBurst` on screen. Firmware source: `firmware/arduino_firmware_updated.ino`.

---

## 1. Hardware capture (on the Arduino)

- **Board**: Arduino GIGA R1 (STM32H7).
- **Sensor input**: pin `A0`, read via the `Arduino_AdvancedAnalog` library (`adc0`).
- **Sample rate**: 250,000 samples/second (250 kSPS) → **4.0 µs per sample**.
- **Resolution**: 16-bit (`AN_RESOLUTION_16`), so each raw sample is `0`–`65535`, converted
  to volts as `rawADC * 3.3 / 65535`.
- **DMA buffering**: 16 buffers of 16 samples each, so the CPU doesn't drop samples during
  the burst.
- A one-time register tweak (`optimizeADCSamplingTime()`) shortens the ADC's per-channel
  sampling time to 64.5 clock cycles, so it can keep up with 250 kSPS cleanly.

### Triggering

An LED (pin 3) blinks on/off every 250 ms as part of the automated "keep pulsing" loop.
The moment the LED goes **LOW** (light cut off), the firmware:
1. Flushes any stale samples sitting in the ADC's buffer.
2. Sets `isTriggered = true` and resets the sample counter.
3. Starts filling `capturedVoltages[]` from the next available ADC buffer.

Capture always collects exactly **700 samples** (`TARGET_SAMPLES`) — a fixed 2.8 ms
window — before `captureDone` is set and the burst moves to the analysis stage.

## 2. On-board analysis (also mirrored in Python)

Once 700 samples are in hand, the firmware:

1. **Finds the peak / trigger point** — scans for the first place the voltage drops by
   at least 50 mV between consecutive samples (`dropThreshold = 0.050`). That index is
   `truePeakIndex`. If nothing crosses the threshold, it defaults to index 0.
2. **Gate check** — the voltage at `truePeakIndex` must be at least **1.0 V**, or the
   whole burst is treated as noise and rejected (`ERROR_BOUNDS_EXCEEDED`).
3. **Picks the regression window**: from `truePeakIndex + 40` to `truePeakIndex + 190`
   (151 samples, skipping the first 40 to avoid circuit ringing right after the trigger).
   That window must fit inside the 700-sample burst, or it's rejected.
4. **Log-linear regression** — for an exponential decay `V(t) = V₀·e^(−t/τ)`, taking the
   log of both sides gives a straight line: `ln(V) = −t/τ + ln(V₀)`. The firmware fits a
   least-squares line to `(t, ln V)` over the regression window (only points where
   `V > 0.05 V`, to avoid `ln(0)`), requiring more than 10 usable points and a
   non-degenerate, negative slope.
5. **Fall time** — defined as the 90%→10% decay time. For an exponential curve that's
   `ln(9) × τ`, i.e.:

   ```
   fall_time_us = 2.1972245 × (−1 / slope)
   ```
6. **Rolling average** — the last 10 successful fall times are kept in a small array and
   averaged (`storedBatchAvg10`), refreshed every 10 valid captures.

**This exact math is reimplemented in Python**, in `core/analysis/fall_time.py`
(`FallTimeCalculator`) — same thresholds, same offsets, same magic constant
(`2.1972245`), same error names (`ERROR_BOUNDS_EXCEEDED`, `ERROR_NOT_ENOUGH_POINTS`,
`ERROR_DENOMINATOR_ZERO`, `ERROR_SLOPE_POSITIVE`). This means the dashboard's BLE path
(and the simulator) compute fall time independently from the raw voltages rather than
trusting a number sent by the firmware, and will get the same answer the firmware would.

## 3. Getting the data to the PC — two transports

The Arduino has a touchscreen mode selector with three states: **Local Only** (nothing
sent to a PC — the decay curve and metrics are drawn directly on the Arduino's own
display), **Remote USB**, and **Remote BLE**. Only the latter two matter for the
dashboard.

### 3.1 USB Serial — text framing

At 115200 baud, the firmware prints the whole 700-sample burst as plain CSV text:

```
<<BEG>>
Sample_Index,Time_us,Voltage_V
0,0.0,2.3120
1,4.0,2.3050
...
699,2796.0,0.0842
<<END>>
```

This is simple and, over a wired USB CDC connection, reliable enough that the dashboard
doesn't need any retry logic — `TraceParser` (see `01_MODELS_AND_PARSER.md`) just buffers
incoming lines and reassembles frames.

### 3.2 BLE — binary packets with retransmission

BLE is different: it's wireless, notification payloads are capped at 20 bytes, and
individual notifications can be silently dropped. Sending 700 samples as one long text
stream over BLE would risk losing an unrecoverable chunk of a burst. Instead, the
firmware and dashboard use the Nordic UART Service profile with a small custom binary
protocol:

**GATT profile**
| | UUID | Type |
|---|---|---|
| Service | `6E400001-B5A3-F393-E0A9-E50E24DCCA9E` | — |
| TX characteristic (Arduino → PC) | `6E400003-...` | Notify |
| RX characteristic (PC → Arduino) | `6E400002-...` | Write |

**Packets, Arduino → PC (over TX, Notify):**

| Packet | Size | Layout |
|---|---|---|
| SAMPLE | 11 bytes | `[type=0x00][index: u16][time_us: f32][voltage: f32]` |
| END | 3 bytes | `[type=0x01][total_count: u16]` |

The firmware sends one SAMPLE packet per sample (700 of them), then one END packet.

**Commands, PC → Arduino (over RX, Write):**

| Command | Byte(s) | Meaning |
|---|---|---|
| `0x01` | START | Begin capturing/streaming |
| `0x02` | STOP | Stop |
| `0x03` | RESEND | `[0x03][count][idx0_lo][idx0_hi]...` — resend up to 8 specific sample indices |
| `0x04` | BURST_ACK | Host confirms it has the complete burst — safe to resume auto-capture |

**Loss recovery (Selective Repeat ARQ)** — on the Python side, `BLEBurstAssembler`
(`core/parser/ble_binary_parser.py`) tracks exactly which sample indices it has received.
When the END packet arrives:

1. If every index 0–699 was received, the burst is complete — done.
2. If some are missing, `BLESource` sends one or more RESEND commands listing just those
   indices (chunked at 8 indices per 20-byte packet), waits ~0.4 s, and checks again.
3. This can repeat up to **5 rounds**. If the burst is still incomplete after 5 rounds,
   it's discarded — with a log line reporting exactly how many/which samples were lost —
   rather than silently storing corrupted data.
4. Either way, the dashboard sends a BURST_ACK once it's done with the burst, so the
   Arduino's auto-capture loop (which otherwise pauses, `awaitingBurstAck`, so it doesn't
   overwrite `capturedVoltages[]` mid-retransmission) can resume. There's also a 3-second
   failsafe timeout on the Arduino side in case the host never ACKs at all.

This is a meaningfully more robust design than a plain text stream over BLE: a single
dropped notification used to mean losing the *entire* burst; now it means, at worst, one
resend round for a handful of samples.

## 4. Python-side reconstruction

- **Serial path**: `SerialSource` → `TraceParser.feed()` → `TraceBurst`, with fall time
  computed inline inside the parser (see `01_MODELS_AND_PARSER.md`).
- **BLE path**: `BLESource` → `BLEBurstAssembler` (gap detection + resend) →
  `FallTimeCalculator.compute()` (same regression as the firmware) → `TraceBurst`.

Either way, the result lands in the shared `burst_queue`, and from there follows the same
path described in `ARCHITECTURE.md` §4 and `04_CONCURRENCY_AND_SERVICES.md`.