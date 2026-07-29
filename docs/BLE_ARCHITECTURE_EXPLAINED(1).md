# How the BLE (Bluetooth) Connection Works — Explained Simply

This document explains `core/sources/ble_source.py` and `core/parser/ble_binary_parser.py` in plain language — what problem BLE creates, how the code solves it, and how data flows from the Arduino to the dashboard.

---

## 1. The core problem: Bluetooth drops packets, USB cable doesn't

Over a USB cable, bytes basically always arrive — it's a wired, physically reliable connection. Bluetooth Low Energy (BLE) is wireless, and wireless links occasionally lose packets — a bit of interference, distance, or timing hiccup, and one notification just never arrives.

For USB Serial, the dashboard doesn't worry about this — it just reads whatever comes in as one continuous text stream (`<<BEG>>` ... CSV lines ... `<<END>>`).

For BLE, that approach would be dangerous: if even **one** sample out of 700 gets silently dropped over the air, and the code just trusted whatever arrived, you'd get a decay curve with a gap in it, or — worse — every sample after the gap shifted one position to the left, corrupting the entire trace without any obvious sign something went wrong.

So BLE needed its own protocol, specifically designed to **notice** when something is missing and **fix it**, rather than a protocol that just hopes nothing gets lost. That's the entire reason `ble_binary_parser.py` exists as a separate thing from the Serial parser.

---

## 2. Why binary, not text?

The Serial protocol sends each sample as a text line: `0,0.0,2.4521`. That's easy to read but wasteful — BLE notifications are tiny (about 20 bytes each), so packing text into them means very few bytes are actual data.

Instead, the BLE protocol packs each sample into a fixed 11-byte binary packet:

```
Byte 0:      packet type (0x00 = "this is a sample")
Bytes 1-2:   sample index    (which of the 700 samples this is)
Bytes 3-6:   time in microseconds (as a decimal number)
Bytes 7-10:  voltage (as a decimal number)
```

That's the whole packet. No commas, no text parsing — just raw numbers, exactly matching how the Arduino firmware packs them on its side. This is deliberately simple: less to go wrong, less bandwidth wasted, and it matches the firmware byte-for-byte so there's no ambiguity about what a packet means.

When all 700 samples have been sent, the Arduino sends one more small packet — the **END** packet — which just says "I'm done, and here's how many samples I *think* I sent" (3 bytes: type = 0x01, plus the count).

---

## 3. The key idea: don't trust, verify — and only re-ask for what's missing

Here's the clever part. Instead of a system where a lost packet just means lost data, the assembler:

1. Keeps a box for each of the 700 expected samples ("slot 0", "slot 1", ... "slot 699"), all empty at first.
2. As sample packets arrive, it puts the value into the matching slot (by index — so order doesn't even matter, packets can arrive slightly out of order and it still works).
3. When the END packet arrives, it checks: **which slots are still empty?**
4. If none are empty — great, the burst is complete, done.
5. If some are empty, it makes a list of exactly those missing sample numbers and asks the Arduino: *"please resend samples #45, #112, #390"* — not the whole burst again, just the specific ones that went missing.
6. It waits a short moment (0.4 seconds) for those to arrive, then checks again.
7. This repeats up to **5 times**. If it's still incomplete after 5 rounds, it gives up on that one burst (discards it) rather than hanging forever waiting for a dead connection.

This approach has a name in networking: **Selective Repeat ARQ** (Automatic Repeat reQuest). "Selective" means you only re-ask for the specific pieces that are missing — not the whole message — which is far more efficient than just re-sending everything whenever anything goes wrong.

**Why this matters in plain terms:** if 2 samples out of 700 get lost over the air, the old naive approach would either silently corrupt the whole burst or throw the whole burst away. This approach asks for exactly those 2 samples back and completes the burst correctly, at the cost of a small delay — a much better trade.

---

## 4. Asking for missing samples — how the "resend request" is packed

Since the Arduino needs to know *exactly which* sample numbers to resend, the dashboard sends a small command packet listing them:

```
Byte 0:        command type (0x03 = "please resend these")
Byte 1:        how many indices follow (up to 8)
Bytes 2-3:     first missing index
Bytes 4-5:     second missing index
...            (and so on)
```

Why only 8 at a time? A single BLE write is capped around 20 bytes, and 8 indices (2 bytes each) plus the 2-byte header fits comfortably inside that limit. If more than 8 samples are missing, the request is automatically split into multiple resend packets rather than trying to cram them into one.

---

## 5. The four commands the dashboard can send

Every command is a tiny, fixed packet — no text, just single bytes (or a few bytes for RESEND):

| Command | Byte | Meaning |
|---|---|---|
| START | `0x01` | "Begin capturing and sending bursts" |
| STOP | `0x02` | "Stop capturing" |
| RESEND | `0x03` + index list | "Please resend these specific missing samples" |
| BURST_ACK | `0x04` | "I've got the complete burst (or given up on it) — go ahead and capture the next one" |

The **ACK** is important: the Arduino won't start looking for the next pulse until it hears BURST_ACK. This is deliberate flow control — it stops the Arduino from racing ahead and sending burst #2 while the dashboard is still busy requesting resends for burst #1.

---

## 6. Why BLE commands don't need their own extra reliability logic

You might wonder: if BLE can drop *sample* packets, can't it also drop a START or STOP *command*? In principle yes — but the code sidesteps this by using a Bluetooth write mode called a **Write Request** (as opposed to a plain "Write Without Response"). A Write Request is acknowledged at the Bluetooth radio level itself — the phone/PC's Bluetooth stack already guarantees it arrived before letting the code move on. So commands (START, STOP, RESEND, ACK) get reliability "for free" from Bluetooth itself, and only the actual sample *data* notifications needed the custom Selective-Repeat logic described above, because those come from the Arduino's side as one-way "notifications," which don't have that same built-in guarantee.

---

## 7. Where this all runs: asyncio in a background thread

BLE communication in Python (via the `bleak` library) is asynchronous — it uses `async`/`await` code (called "asyncio"), which normally runs its own dedicated event loop. But the dashboard's GUI (CustomTkinter) also needs its own main-thread loop to stay responsive. Two different "main loops" can't share one thread.

The solution: `BLESource` spins up a completely separate background thread whose only job is to run the asyncio event loop and handle all BLE communication. The GUI thread never talks to Bluetooth directly — it just puts a finished `TraceBurst` onto a thread-safe queue, and the main GUI thread picks it up from there on its normal 100ms timer (the same queue mechanism used for Serial and the Simulator — see `04_CONCURRENCY_AND_SERVICES.md`). This keeps the BLE connection's async complexity completely isolated from the rest of the app.

---

## 8. Step-by-step: the full life of one burst over BLE

1. **Connect** — the app scans for a BLE device whose advertised name matches the configured `device_name` (default `GIGA_WORKSTATION`), connects to it, and subscribes to notifications.
2. **Start** — the app resets the assembler (`start_new_burst()`) and sends the START command.
3. **Arduino detects a pulse** and starts streaming 700 SAMPLE packets, one per data point, followed by one END packet.
4. **Each SAMPLE packet** that arrives gets unpacked and dropped into its matching slot by index.
5. **The END packet arrives** — the app checks whether all 700 slots are filled.
6. **If anything is missing**, it sends a RESEND request for exactly those indices, waits briefly, and re-checks — repeating up to 5 times.
7. **Once complete** (or after giving up), the app:
   - Runs the *exact same* fall-time regression math the firmware itself uses (`core/analysis/fall_time.py`) on the raw voltage array — it never just trusts a number the firmware might have sent, it recomputes fall time and peak voltage itself from the raw samples.
   - Builds a `TraceBurst` object and puts it on the queue for the GUI to pick up.
   - Sends BURST_ACK so the Arduino is free to start looking for the next pulse.
   - Resets the assembler, ready for the next burst.

---

## 9. Why this design is worth the extra complexity

It would have been simpler to just reuse the same text protocol (`<<BEG>>`/`<<END>>`) over BLE too. The reason that wasn't done: over a wired USB connection, dropped bytes are rare enough to ignore. Over BLE, they're common enough that ignoring them would mean **regularly losing or corrupting real experimental data** — which, for a measurement instrument, is a much worse outcome than a bit of extra code complexity. The binary protocol with Selective-Repeat ARQ trades a small amount of engineering effort for data integrity, which is the right trade for anything meant to produce trustworthy measurements.

---

## 10. Quick summary (one paragraph version)

BLE can lose packets, so instead of just trusting whatever arrives, the dashboard tracks exactly which of the 700 expected samples per burst have shown up, and when the Arduino signals "done," it checks for gaps and asks — by exact sample number — for only the missing ones to be resent, repeating up to 5 times before giving up on that burst. Everything (samples, commands) is sent as small fixed binary packets instead of text, matching the firmware's own format byte-for-byte. All of this runs on its own background thread using Python's asyncio, so it never blocks the GUI, and the final result — a complete burst — is handed off through the same thread-safe queue the Simulator and Serial sources use, so the rest of the app doesn't need to know or care which transport actually delivered the data.
