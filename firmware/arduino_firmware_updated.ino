#include <Arduino_AdvancedAnalog.h>
#include <Arduino_H7_Video.h>
#include <Arduino_GigaDisplay_GFX.h>
#include <Arduino_GigaDisplayTouch.h>
#include <math.h>
#include <ArduinoBLE.h>

// Hardware Pins
const int ledPin = 3;
AdvancedADC adc0(A0);

// Global Video Driver Configuration
Arduino_H7_Video Display(800, 480);

// Display & Touch Initialization
GigaDisplay_GFX tft;
Arduino_GigaDisplayTouch touch;

// RGB565 Colors
#define COLOR_RED 0xF800
#define COLOR_GREEN 0x07E0
#define COLOR_WHITE 0xFFFF
#define COLOR_BLACK 0x0000
#define COLOR_CYAN 0x07FF
#define COLOR_YELLOW 0xFFE0
#define COLOR_GRAY 0x7BEF

#define COLOR_SKYBLUE 0x03FF
#define COLOR_ORANGE 0xFBE0
#define COLOR_MAGENTA 0xF81F

const uint32_t SAMPLE_RATE = 250000;
const float US_PER_SAMPLE = 4.0;

const int N_SAMPLES = 16;
const int N_BUFFERS = 16;

const int TARGET_SAMPLES = 700;
float capturedVoltages[TARGET_SAMPLES];
int totalSamplesCollected = 0;

bool systemActive = false;
bool isTriggered = false;
bool captureDone = false;
bool ledState = LOW;
unsigned long executionCycleCount = 0;

enum DataRoute {
  ROUTE_LOCAL_ONLY,
  ROUTE_REMOTE_USB,
  ROUTE_REMOTE_BLE
};
DataRoute currentRoute = ROUTE_LOCAL_ONLY;
bool bleInitialized = false;

// ===== BLE UART profile: TX (notify) + RX (write) =====
BLEService uartService("6E400001-B5A3-F393-E0A9-E50E24DCCA9E");
BLECharacteristic txCharacteristic("6E400003-B5A3-F393-E0A9-E50E24DCCA9E", BLENotify, 20);
BLECharacteristic rxCharacteristic("6E400002-B5A3-F393-E0A9-E50E24DCCA9E", BLEWrite, 20);

// ===== Binary packet protocol (BLE only; USB Serial keeps CSV) =====
// SAMPLE packet (11 bytes):  [0]=0x00  [1-2]=sample_index(u16 LE)  [3-6]=time_us(f32 LE)  [7-10]=voltage(f32 LE)
// END packet    (3 bytes):   [0]=0x01  [1-2]=total_count(u16 LE)
#pragma pack(push, 1)
struct SamplePacket {
  uint8_t type;      // 0x00
  uint16_t index;
  float time_us;
  float voltage;
};
struct EndPacket {
  uint8_t type;      // 0x01
  uint16_t total_count;
};
#pragma pack(pop)

// ================= COMMAND PROTOCOL =================
//
// BLE:
// 0x01 START
// 0x02 STOP
// 0x03 RESEND
// 0x04 BURST ACK
// 0x05 SET LOCAL MODE
// 0x06 SET USB MODE
// 0x07 SET BLE MODE
//
// Serial:
// START
// STOP
// MODE LOCAL
// MODE USB
// MODE BLE
//
#define CMD_START          0x01
#define CMD_STOP           0x02
#define CMD_RESEND         0x03
#define CMD_BURST_ACK      0x04
#define CMD_SET_LOCAL_MODE 0x05
#define CMD_SET_USB_MODE   0x06
#define CMD_SET_BLE_MODE   0x07

// Gate that pauses the automated re-trigger engine while a burst is in flight
// over BLE and might still need retransmission from capturedVoltages[].
bool awaitingBurstAck = false;
unsigned long burstSentAtMillis = 0;
const unsigned long BURST_ACK_TIMEOUT_MS = 3000; // failsafe if host never ACKs

const unsigned long lastTouchTime_UNUSED = 0; // placeholder to keep numbering stable
unsigned long lastTouchTime = 0;
const unsigned long touchLockoutInterval = 200;

unsigned long previousBlinkMillis = 0;
const long blinkInterval = 250;

unsigned long lastDisplayUpdateTime = 0;
const unsigned long displayUpdateInterval = 50;

float fallTimeHistory[10];
int totalValidCaptures = 0;
int historyWriteIndex = 0;
float storedBatchAvg10 = -1.0;

const int btnX = 60;
const int btnY = 110;
const int btnW = 320;
const int btnH = 80;

const int txBtnX = 420;
const int txBtnY = 110;
const int txBtnW = 320;
const int txBtnH = 80;

const int graphX = 420;
const int graphY = 430;
const int graphW = 340;
const int graphH = 170;

void optimizeADCSamplingTime() {
#if defined(ADC1)
  ADC1->SMPR2 &= ~(0x7UL << 15);
  ADC1->SMPR2 |= (0x4UL << 15);
  Serial.println(">>> REGISTER OPTIMIZATION SUCCESSFUL: ADC1 Channel 15 set to 64.5 cycles.");
#else
  Serial.println(">>> REGISTER ERROR: Hardware architecture mismatch.");
#endif
}

void drawButton(bool activeState) {
  tft.setTextSize(3);
  if (activeState == true) {
    tft.fillRect(btnX, btnY, btnW, btnH, COLOR_RED);
    tft.setCursor(btnX + 115, btnY + 28);
    tft.setTextColor(COLOR_WHITE);
    tft.print("STOP");
  } else {
    tft.fillRect(btnX, btnY, btnW, btnH, COLOR_GREEN);
    tft.setCursor(btnX + 110, btnY + 28);
    tft.setTextColor(COLOR_BLACK);
    tft.print("START");
  }
}

void drawTxModeButton() {
  tft.setTextSize(2);
  tft.setTextColor(COLOR_WHITE);

  if (currentRoute == ROUTE_LOCAL_ONLY) {
    tft.fillRect(txBtnX, txBtnY, txBtnW, txBtnH, COLOR_SKYBLUE);
    tft.setCursor(txBtnX + 70, txBtnY + 22);
    tft.print("SYSTEM MODE:");
    tft.setCursor(txBtnX + 85, txBtnY + 44);
    tft.print("LOCAL ONLY");
  } else if (currentRoute == ROUTE_REMOTE_USB) {
    tft.fillRect(txBtnX, txBtnY, txBtnW, txBtnH, COLOR_ORANGE);
    tft.setCursor(txBtnX + 70, txBtnY + 22);
    tft.print("REMOTE MODE:");
    tft.setCursor(txBtnX + 75, txBtnY + 44);
    tft.print("USB TX ACTIVE");
  } else if (currentRoute == ROUTE_REMOTE_BLE) {
    tft.fillRect(txBtnX, txBtnY, txBtnW, txBtnH, COLOR_MAGENTA);
    tft.setCursor(txBtnX + 70, txBtnY + 22);
    tft.print("REMOTE MODE:");
    tft.setCursor(txBtnX + 30, txBtnY + 44);

    if (bleInitialized && BLE.central() && BLE.central().connected()) {
      tft.print("BLE UART (CONNECTED)");
    } else {
      tft.print("BLE UART (PAIRING...)");
    }
  }
}

void drawGraphCanvas() {
  tft.drawRect(graphX, graphY - graphH, graphW, graphH, COLOR_GRAY);

  for (int i = 1; i < 4; i++) {
    int lineY = (graphY - graphH) + ((graphH / 4) * i);
    for (int lineX = graphX + 4; lineX < (graphX + graphW); lineX += 8) {
      tft.drawFastHLine(lineX, lineY, 4, 0x3186);
    }
  }

  tft.setTextSize(2);
  tft.setTextColor(COLOR_YELLOW);
  tft.setCursor(graphX - 55, graphY - graphH + 2);
  tft.print("3.3V-");
  tft.setCursor(graphX - 55, graphY - (graphH / 2) - 7);
  tft.print("1.6V-");
  tft.setCursor(graphX - 55, graphY - 14);
  tft.print("0.0V-");

  tft.setTextColor(COLOR_WHITE);
  tft.setCursor(graphX, graphY + 12);
  tft.print("0 us");

  tft.setCursor(graphX + graphW - 75, graphY + 12);
  tft.print("900 us");

  tft.setCursor(graphX + (graphW / 2) - 60, graphY + 12);
  tft.setTextColor(COLOR_CYAN);
  tft.print("TIME WINDOW");
}

void updateDisplayMetrics(float peakVolts, float currentFallTimeUs, float batchAvgFallTimeUs) {
  tft.setTextSize(3);

  tft.fillRect(60, 265, 290, 35, COLOR_BLACK);
  tft.setTextColor(COLOR_YELLOW);
  tft.setCursor(60, 265);
  tft.print("Peak: ");
  if (peakVolts >= 0.0) {
    tft.print(peakVolts, 3);
    tft.print(" V");
  } else {
    tft.print("---");
  }

  tft.fillRect(60, 325, 290, 35, COLOR_BLACK);
  tft.setTextColor(COLOR_CYAN);
  tft.setCursor(60, 325);
  tft.print("Fall: ");
  if (currentFallTimeUs > 0.0) {
    tft.print(currentFallTimeUs, 1);
    tft.print(" us");
  } else if (currentFallTimeUs == -1.0) {
    tft.print("---");
  } else {
    tft.setTextColor(COLOR_RED);
    tft.print("ERROR");
  }

  tft.fillRect(60, 385, 290, 35, COLOR_BLACK);
  tft.setTextColor(COLOR_WHITE);
  tft.setCursor(60, 385);
  tft.print("Avg: ");
  if (batchAvgFallTimeUs > 0.0) {
    tft.print(batchAvgFallTimeUs, 1);
    tft.print(" us");
  } else {
    tft.print("---");
  }
}

void plotDecayCurveLocalOnly() {
  if (currentRoute != ROUTE_LOCAL_ONLY) return;

  tft.fillRect(graphX + 1, graphY - graphH + 1, graphW - 2, graphH - 2, COLOR_BLACK);

  int truePeakIndex = 0;
  float dropThreshold = 0.050;
  for (int i = 0; i < TARGET_SAMPLES - 1; i++) {
    if ((capturedVoltages[i] - capturedVoltages[i + 1]) >= dropThreshold) {
      truePeakIndex = i;
      break;
    }
  }

  int startPlotIdx = max(0, truePeakIndex - 10);
  int plotSpan = 225;

  float prevX = graphX;
  float firstOffset = (capturedVoltages[startPlotIdx] / 3.3) * (graphH - 10);
  float prevY = graphY - 5 - firstOffset;

  for (int i = 1; i < plotSpan; i++) {
    int currentDataIdx = startPlotIdx + i;
    if (currentDataIdx >= TARGET_SAMPLES) break;

    float xPos = (float)graphX + (((float)i * (float)graphW) / (float)plotSpan);
    float yOffset = (capturedVoltages[currentDataIdx] / 3.3) * (float)(graphH - 10);
    float yPos = (float)graphY - 5.0 - yOffset;

    if (yPos < (float)(graphY - graphH + 2)) yPos = (float)(graphY - graphH + 2);
    if (yPos > (float)(graphY - 2)) yPos = (float)(graphY - 2);

    tft.drawLine((int)prevX, (int)prevY, (int)xPos, (int)yPos, COLOR_CYAN);

    prevX = xPos;
    prevY = yPos;
  }
}

void clearLowerPanelStateContext() {
  tft.fillRect(0, 250, 800, 230, COLOR_BLACK);

  if (currentRoute == ROUTE_LOCAL_ONLY) {
    updateDisplayMetrics(-1.0, -1.0, -1.0);
    drawGraphCanvas();
  } else {
    if (systemActive) {
      tft.setTextSize(3);
      tft.setTextColor(COLOR_GRAY);
      tft.setCursor(240, 330);
      tft.print("Processing Remotely...");
    } else {
      updateDisplayMetrics(-1.0, -1.0, -1.0);
    }
  }
}

// ===== Shared start/stop logic, callable from touchscreen AND BLE command =====
void activateSystem(bool newState) {
  systemActive = newState;
  drawButton(systemActive);

  if (!systemActive) {
    ledState = LOW;
    digitalWrite(ledPin, ledState);
    isTriggered = false;
    totalSamplesCollected = 0;
    totalValidCaptures = 0;
    historyWriteIndex = 0;
    storedBatchAvg10 = -1.0;
    awaitingBurstAck = false;
    clearLowerPanelStateContext();
    drawTxModeButton();
  } else {
    previousBlinkMillis = millis();
    clearLowerPanelStateContext();
  }
}

// Handle incoming Serial commands from PC dashboard
void handleSerialCommands() {
  if (!Serial.available())
    return;
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  if (cmd.equalsIgnoreCase("START")) {
    if (!systemActive)
      activateSystem(true);
    return;
  }
  if (cmd.equalsIgnoreCase("STOP")) {
    if (systemActive)
      activateSystem(false);
    return;
  }
  if (cmd.equalsIgnoreCase("MODE LOCAL")) {
    currentRoute = ROUTE_LOCAL_ONLY;
    clearLowerPanelStateContext();
    drawTxModeButton();
    return;
  }
  if (cmd.equalsIgnoreCase("MODE USB")) {
    currentRoute = ROUTE_REMOTE_USB;
    clearLowerPanelStateContext();
    drawTxModeButton();
    return;
  }
  if (cmd.equalsIgnoreCase("MODE BLE")) {
    currentRoute = ROUTE_REMOTE_BLE;
    clearLowerPanelStateContext();
    drawTxModeButton();
    return;
  }
}

// ===== Send one sample as an 11-byte binary packet over BLE Notify =====
void sendSamplePacketBLE(int index) {
  SamplePacket pkt;
  pkt.type = 0x00;
  pkt.index = (uint16_t)index;
  pkt.time_us = index * US_PER_SAMPLE;
  pkt.voltage = capturedVoltages[index];
  txCharacteristic.writeValue((uint8_t*)&pkt, sizeof(SamplePacket));
}

// ===== Handle an incoming command written to rxCharacteristic =====
void handleIncomingCommand() {
  int len = rxCharacteristic.valueLength();
  if (len <= 0) return;

  uint8_t buf[20];
  int copyLen = min(len, (int)sizeof(buf));
  memcpy(buf, rxCharacteristic.value(), copyLen);

  uint8_t cmd = buf[0];

  // START acquisition
  if (cmd == CMD_START) {
      if (!systemActive)
          activateSystem(true);
  }
  // STOP acquisition
  else if (cmd == CMD_STOP) {
      if (systemActive)
          activateSystem(false);
  }
  // Switch to LOCAL mode
  else if (cmd == CMD_SET_LOCAL_MODE) {
      currentRoute = ROUTE_LOCAL_ONLY;
      clearLowerPanelStateContext();
      drawTxModeButton();
  }
  // Switch to USB mode
  else if (cmd == CMD_SET_USB_MODE) {
      currentRoute = ROUTE_REMOTE_USB;
      clearLowerPanelStateContext();
      drawTxModeButton();
  }
  // Switch to BLE mode
  else if (cmd == CMD_SET_BLE_MODE) {
      currentRoute = ROUTE_REMOTE_BLE;
      clearLowerPanelStateContext();
      drawTxModeButton();
  }

  } else if (cmd == CMD_BURST_ACK) {
    awaitingBurstAck = false;

  } else if (cmd == CMD_RESEND) {
    if (copyLen < 2) return;
    uint8_t count = buf[1];
    int available = (copyLen - 2) / 2;
    count = min((int)count, available);

    for (int i = 0; i < count; i++) {
      uint16_t idx = buf[2 + i * 2] | (buf[2 + i * 2 + 1] << 8);
      if (idx < TARGET_SAMPLES) {
        sendSamplePacketBLE(idx);
        delayMicroseconds(500);
      }
    }
  }
}

void setup() {
  Serial.begin(115200);

  uint32_t startCheck = millis();
  while (!Serial) {
    if (millis() - startCheck > 3500) break;
  }

  pinMode(ledPin, OUTPUT);
  digitalWrite(ledPin, ledState);

  tft.begin();
  tft.setRotation(1);

  if (touch.begin()) {
    Serial.println("Touch controller initialized successfully.");
  } else {
    Serial.println("Error: Touch controller initialization failed.");
  }

  tft.fillScreen(COLOR_BLACK);

  tft.setTextSize(4);
  tft.setTextColor(COLOR_WHITE);
  tft.setCursor(70, 35);
  tft.print("Photodetector Decay Analyzer");

  tft.setTextSize(2);
  tft.setTextColor(COLOR_CYAN);
  tft.setCursor(100, 230);
  tft.print("--- LOCAL ACCELERATED METRICS DISPLAY ---");

  if (BLE.begin()) {
    BLE.setLocalName("GIGA_WORKSTATION");
    BLE.setDeviceName("GIGA_WORKSTATION");
    BLE.setAppearance(0x0000);

    uartService.addCharacteristic(txCharacteristic);
    uartService.addCharacteristic(rxCharacteristic);
    BLE.addService(uartService);

    BLE.setConnectionInterval(0x000C, 0x0024);
    BLE.advertise();
    bleInitialized = true;
    Serial.println("BLE UART Stack initialized successfully in background.");
  }

  drawButton(systemActive);
  drawTxModeButton();
  drawGraphCanvas();
  updateDisplayMetrics(-1.0, -1.0, -1.0);

  if (!adc0.begin(AN_RESOLUTION_16, SAMPLE_RATE, N_SAMPLES, N_BUFFERS)) {
    Serial.println("CRITICAL ERROR: Advanced ADC setup failed.");
    while (1);
  }

  optimizeADCSamplingTime();
  previousBlinkMillis = millis();
}

void loop() {
  handleSerialCommands();
  unsigned long currentMillis = millis();

  // BLE central connection status poll (unchanged)
  if (currentRoute == ROUTE_REMOTE_BLE && bleInitialized && (currentMillis % 500 == 0)) {
    static bool lastBleConnState = false;
    bool currentBleConnState = BLE.central() && BLE.central().connected();
    if (currentBleConnState != lastBleConnState) {
      lastBleConnState = currentBleConnState;
      drawTxModeButton();
    }
  }

  // Incoming BLE command (START/STOP/RESEND/BURST_ACK)
  if (bleInitialized && rxCharacteristic.written()) {
    handleIncomingCommand();
  }

  // Failsafe: if host never sends BURST_ACK, don't stall forever
  if (awaitingBurstAck && (currentMillis - burstSentAtMillis > BURST_ACK_TIMEOUT_MS)) {
    awaitingBurstAck = false;
  }

  // 1. TOUCH SCREEN ENGINE
  GDTpoint_t points;
  uint8_t contacts = touch.getTouchPoints(&points);
  if (contacts > 0) {
    int touchX = 0;
    int touchY = 0;

    if (points.x > 480) {
      touchX = points.x;
      touchY = points.y;
    } else {
      touchX = points.y;
      touchY = points.x;
    }

    bool hitVisualButton = (touchX >= (btnX - 5) && touchX <= (btnX + btnW + 5) && touchY >= (btnY - 5) && touchY <= (btnY + btnH - 5));
    bool hitAltButton = (touchX >= (btnX - 5) && touchX <= (btnX + btnW + 5) && (480 - touchY) >= (btnY - 5) && (480 - touchY) <= (btnY + btnH - 5));

    bool hitTxModeButton = (touchX >= (txBtnX - 5) && touchX <= (txBtnX + txBtnW + 5) && touchY >= (txBtnY - 5) && touchY <= (txBtnY + txBtnH - 5));
    bool hitAltTxMode = (touchX >= (txBtnX - 5) && touchX <= (txBtnX + txBtnW + 5) && (480 - touchY) >= (txBtnY - 5) && (480 - touchY) <= (txBtnY + txBtnH - 5));

    if (hitTxModeButton || hitAltTxMode) {
      if (currentMillis - lastTouchTime >= touchLockoutInterval) {
        if (currentRoute == ROUTE_LOCAL_ONLY) {
          currentRoute = ROUTE_REMOTE_USB;
        } else if (currentRoute == ROUTE_REMOTE_USB) {
          currentRoute = ROUTE_REMOTE_BLE;
        } else {
          currentRoute = ROUTE_LOCAL_ONLY;
        }
        clearLowerPanelStateContext();
        drawTxModeButton();
        lastTouchTime = currentMillis;
      }
    }

    if (hitVisualButton || hitAltButton) {
      if (currentMillis - lastTouchTime >= touchLockoutInterval) {
        activateSystem(!systemActive);
        lastTouchTime = currentMillis;
      }
    }
  }

  // 2. AUTOMATED CONTINUOUS PULSING ENGINE
  // Paused while a BLE burst is still awaiting host ACK, so capturedVoltages[]
  // is not overwritten mid-retransmission.
  if (systemActive && !awaitingBurstAck) {
    if (currentMillis - previousBlinkMillis >= blinkInterval) {
      previousBlinkMillis = currentMillis;
      ledState = !ledState;
      digitalWrite(ledPin, ledState);

      if (ledState == LOW && !captureDone) {
        while (adc0.available()) {
          SampleBuffer staleBuf = adc0.read();
          staleBuf.release();
        }
        isTriggered = true;
        totalSamplesCollected = 0;
      }
    }
  }

  // 3. HIGH-SPEED ADC PIPELINE PROCESSING
  if (adc0.available()) {
    SampleBuffer buf = adc0.read();

    if (systemActive && isTriggered && !captureDone) {
      for (int i = 0; i < N_SAMPLES; i++) {
        if (totalSamplesCollected < TARGET_SAMPLES) {
          uint16_t rawADC = buf[i];
          capturedVoltages[totalSamplesCollected] = (rawADC * 3.3) / 65535.0;
          totalSamplesCollected++;
        }
      }
      buf.release();

      if (totalSamplesCollected >= TARGET_SAMPLES) {
        captureDone = true;
      }
    } else {
      buf.release();
    }
  }

  // 4. LIVE REGRESSION (LOCAL DISPLAY ONLY) + DATA ROUTING
  if (captureDone && systemActive) {
    int truePeakIndex = 0;
    float dropThreshold = 0.050;
    bool peakValidated = false;

    for (int i = 0; i < TARGET_SAMPLES - 1; i++) {
      if ((capturedVoltages[i] - capturedVoltages[i + 1]) >= dropThreshold) {
        truePeakIndex = i;
        peakValidated = true;
        break;
      }
    }

    if (!peakValidated) truePeakIndex = 0;
    float peakStartVoltage = capturedVoltages[truePeakIndex];

    if (peakStartVoltage >= 1.0) {
      executionCycleCount++;

      int regStartIdx = truePeakIndex + 40;
      int regEndIdx = truePeakIndex + 190;
      float fallTimeRegUs = -1.0;

      if (regEndIdx < TARGET_SAMPLES) {
        float sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;
        int nPoints = 0;

        for (int i = regStartIdx; i <= regEndIdx; i++) {
          float voltage = capturedVoltages[i];
          if (voltage > 0.05) {
            float t = (i - regStartIdx) * US_PER_SAMPLE;
            float lnV = log(voltage);
            sumX += t;
            sumY += lnV;
            sumXY += t * lnV;
            sumX2 += t * t;
            nPoints++;
          }
        }

        if (nPoints > 10) {
          float denominator = (nPoints * sumX2) - (sumX * sumX);
          if (abs(denominator) > 1e-4) {
            float slopeM = ((nPoints * sumXY) - (sumX * sumY)) / denominator;
            if (slopeM < 0) {
              fallTimeRegUs = 2.1972245 * (-1.0 / slopeM);

              fallTimeHistory[historyWriteIndex] = fallTimeRegUs;
              historyWriteIndex++;
              totalValidCaptures++;

              if (historyWriteIndex >= 10) {
                float totalBatchSum = 0;
                for (int k = 0; k < 10; k++) {
                  totalBatchSum += fallTimeHistory[k];
                }
                storedBatchAvg10 = totalBatchSum / 10.0;
                historyWriteIndex = 0;
              }

              // ===== DATA ROUTING =====

              // ROUTE A: USB Serial keeps the original CSV framing untouched.
              if (currentRoute == ROUTE_REMOTE_USB) {
                Serial.println("<<BEG>>");
                Serial.println("Sample_Index,Time_us,Voltage_V");
                for (int i = 0; i < TARGET_SAMPLES; i++) {
                  float sampleTimeUs = i * US_PER_SAMPLE;
                  float sampleVoltage = capturedVoltages[i];
                  Serial.print(i); Serial.print(",");
                  Serial.print(sampleTimeUs, 1); Serial.print(",");
                  Serial.println(sampleVoltage, 4);
                }
                Serial.println("<<END>>");
                Serial.flush();
              }

              // ROUTE B: BLE now sends binary packets, one per sample, then an END marker.
              else if (currentRoute == ROUTE_REMOTE_BLE && bleInitialized && BLE.central() && BLE.central().connected()) {
                for (int i = 0; i < TARGET_SAMPLES; i++) {
                  sendSamplePacketBLE(i);
                }
                EndPacket endPkt;
                endPkt.type = 0x01;
                endPkt.total_count = (uint16_t)TARGET_SAMPLES;
                txCharacteristic.writeValue((uint8_t*)&endPkt, sizeof(EndPacket));

                // Pause auto re-triggering until host ACKs or timeout fires.
                awaitingBurstAck = true;
                burstSentAtMillis = currentMillis;
              }

              // ===== LOCAL DISPLAY (unaffected by remote routes) =====
              if (currentRoute == ROUTE_LOCAL_ONLY) {
                if (currentMillis - lastDisplayUpdateTime >= displayUpdateInterval) {
                  updateDisplayMetrics(peakStartVoltage, fallTimeRegUs, storedBatchAvg10);
                  plotDecayCurveLocalOnly();
                  lastDisplayUpdateTime = currentMillis;
                }
              }

            } else {
              Serial.print("ERROR_SLOPE_POSITIVE");
            }
          } else {
            Serial.print("ERROR_DENOMINATOR_ZERO");
          }
        } else {
          Serial.print("ERROR_NOT_ENOUGH_POINTS");
        }
      } else {
        Serial.print("ERROR_BOUNDS_EXCEEDED");
      }

      Serial.println();
      Serial.flush();
    }

    isTriggered = false;
    totalSamplesCollected = 0;
    captureDone = false;
  }
}
