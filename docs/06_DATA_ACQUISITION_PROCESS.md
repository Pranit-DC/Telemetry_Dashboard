# Data Acquisition (DAQ) System Detail

This document provides a highly detailed explanation of the end-to-end Data Acquisition (DAQ) pipeline—from raw hardware ADC register configurations on the Arduino GIGA R1 to thread-safe parsing and visualization in the Python dashboard.

---

## 1. Hardware-Level ADC Configuration & Optimization

The system samples decay events using an **Arduino GIGA R1** running an STM32H7 microcontroller.

### ADC Resolution & Buffer Settings
In `setup()`, the ADC is configured using the `Arduino_AdvancedAnalog` library:
- **Pin**: `A0` (mapped to `adc0`)
- **Resolution**: `AN_RESOLUTION_16` (16-bit resolution, yielding integer values from `0` to `65535`)
- **Sampling Rate**: `250,000 Hz` (250 kSPS), corresponding to exactly `4.0 µs` per sample.
- **DMA Buffers**: Configured with 16 buffers, each storing 16 samples (`N_SAMPLES = 16`, `N_BUFFERS = 16`). This DMA queue prevents the CPU from dropping samples during high-speed acquisition.

### Sampling Time Register Optimization
The ADC's default sampling time is too slow to support a clean 250 kSPS rate without signal distortion. To resolve this, `optimizeADCSamplingTime()` modifies the STM32 hardware registers directly:
```c
ADC1->SMPR2 &= ~(0x7UL << 15); // Clear bits for Channel 15
ADC1->SMPR2 |= (0x4UL << 15);  // Set sampling time to 64.5 ADC clock cycles
```
This forces the ADC channel to settle faster, ensuring precise voltage readings at high speeds.

---

## 2. Triggering & Decay Capture Logic

The system utilizes an automated, non-blocking pulsing engine to trigger decay events:

```
         ┌── 250ms Blink Window ──┐
LED Pin: ───┐                     ┌───
            │                     │
            └── Decay Event Window ──
Trigger:    ↑ (Falling edge)
            Stale ADC buffers cleared,
            Capture begins.
```

1. **LED Pulsing (Pin 3)**:
   - A non-blocking timer toggles the LED state every `250 ms`.
   - When the LED turns **HIGH**, the photodiode receives maximum light (excitation).
   - When the LED falls **LOW**, the light is cut off, initiating the exponential decay.

2. **Trigger Window Activation**:
   - The moment the LED pin transitions to `LOW`, `isTriggered` is set to `true`, and `totalSamplesCollected` resets to `0`.
   - Before capturing points, the DMA queue is cleared by reading and releasing all existing stale buffers:
     ```c
     while (adc0.available()) {
       SampleBuffer staleBuf = adc0.read();
       staleBuf.release();
     }
     ```

3. **Data Collection**:
   - The main loop reads new DMA buffers.
   - For every 16-bit ADC sample, the raw integer value is converted to a physical voltage:
     $$V = \frac{\text{rawADC} \times 3.3\,\text{V}}{65535}$$
   - Voltages are saved into the `capturedVoltages` array until exactly `700` samples are collected (representing a `2.8 ms` capture window). At that point, `captureDone` is set to `true`.

---

## 3. Onboard Regression & Validation

Once `700` samples are captured, the Arduino validates the transient waveform and runs a log-linear regression to determine the fall time.

### Peak Detection & Validation Gating
To isolate the start of the decay:
1. The firmware scans the array looking for a voltage drop threshold of `50 mV` between successive samples:
   $$V_i - V_{i+1} \ge 0.050\,\text{V}$$
2. The index where this condition is first met is labeled `truePeakIndex`. If no drop is found, it defaults to `0`.
3. **Gating Check**: To prevent noise from triggering calculations on flat/empty signals, the peak start voltage must be at least `1.0 V`:
   $$V_{\text{peak}} \ge 1.0\,\text{V}$$
   If this threshold isn't met, the capture cycle is rejected, and the variables reset.

### Log-Linear Regression Mathematics
To calculate the decay constant $\tau$ without performing expensive non-linear fits, the system linearizes the exponential equation:
$$V(t) = V_0 e^{-t/\tau}$$
Taking the natural logarithm of both sides:
$$\ln(V) = -\frac{1}{\tau}t + \ln(V_0)$$
This matches the linear equation $y = mt + c$, where:
- $y = \ln(V)$
- $x = t$ (time in microseconds, starting at $0$ at `regStartIdx`)
- $m = -\frac{1}{\tau}$ (slope)

**Data Window**:
- **Start**: `truePeakIndex + 40` (skips initial circuit stabilization/ringing)
- **End**: `truePeakIndex + 190`
- **Total Points ($n$)**: Up to 151 points, ignoring any point where $V \le 0.05\,\text{V}$ (to avoid log of zero/noise floor).

**Regression Calculations**:
The firmware calculates the cumulative variables:
$$\sum x, \quad \sum y, \quad \sum xy, \quad \sum x^2$$
The slope ($m$) is computed via the least-squares formula:
$$m = \frac{n\sum xy - \sum x \sum y}{n\sum x^2 - (\sum x)^2}$$

### Fall-Time Calculation
The fall time ($t_{\text{fall}}$) is defined as the time it takes for the voltage to decay from 90% to 10% of its peak.
For an exponential decay:
$$t_{\text{fall}} = \ln(9) \times \tau \approx 2.1972245 \times \left(-\frac{1}{m}\right)$$

---

## 4. Multi-Route Telemetry Protocol

Depending on the routing mode selected on the GIGA touch screen, data is packaged and sent using distinct protocols:

### ROUTE A: Native USB Serial
Data is printed as ASCII strings to the serial port at `115200` baud:
```text
<<BEG>>
Sample_Index,Time_us,Voltage_V
40,0.0,2.1523
41,4.0,2.0234
...
<<END>>
```

### ROUTE B: BLE (Bluetooth Low Energy) UART
To fit within the **20-byte BLE Characteristic MTU limit** without truncation, the data is structured as follows:
1. **Sentinels**: Written directly as single-packet notification updates:
   - `<<BEG>>\n` (8 bytes)
   - `Index,Time,Volt\n` (16 bytes)
2. **Numeric Data Points**: Formatted into strings (e.g., `"140,400.0,1.2543\n"`), and then manually chunked into 20-byte packets using a loop:
   ```c
   int bytesSent = 0;
   while (bytesSent < msgLength) {
     int chunkSize = min(20, msgLength - bytesSent);
     txCharacteristic.writeValue((uint8_t*)&bleTxBuffer[bytesSent], chunkSize);
     bytesSent += chunkSize;
     delayMicroseconds(500);
   }
   ```
3. **Closing Sentinel**: Written as `<<END>>\n` (8 bytes).

---

## 5. Python-Side Parsing & Queue Management

The desktop dashboard handles incoming telemetry using a dedicated parsing state machine.

```
       [ Raw Text Stream ]
               │
               ▼
       [ Split on '\n' ]
               │
   ┌───────────┴───────────┐
   ▼                       ▼
<<BEG>>                 <<END>>
State ──► 'in_frame'    State ──► 'idle'
Clear buffers           Calculate local fallback metrics;
                        Emit completed TraceBurst
```

1. **Stream Buffering (`TraceParser.feed`)**:
   - Incoming chunks from the serial interface or BLE characteristic are appended to `_line_buffer`.
   - The buffer is split on `\n`. The last fragment (if it doesn't end with a newline) is saved back to `_line_buffer` to await the next packet.

2. **State Machine Transitions**:
   - **`<<BEG>>`**: Sets state to `in_frame` and clears point buffers.
   - **CSV Data (`idx,time,volt`)**: If state is `in_frame`, the line is split by `,`. The strings are converted into floats and appended as a `TracePoint`. If a line contains header text, it throws a `ValueError` during parsing and is safely skipped.
   - **`<<END>>`**: Sets state to `idle`. It packages the collected list of `TracePoint`s into a `TraceBurst` object, performs regression calculation fallbacks if hardware metrics are missing, and returns the completed burst.

3. **Acquisition Dispatching**:
   - Completed `TraceBurst` instances are pushed to a thread-safe `queue.Queue`.
   - The dashboard GUI polls this queue every `100 ms` via a Tkinter `.after()` callback.
   - For every pulled burst, the system:
     1. Writes the trace metadata and points to the SQLite database (using WAL journal mode).
     2. Appends summary records to the daily csv log file.
     3. Notifies the Matplotlib rendering thread to redraw the decay trace and trend line graphs.
