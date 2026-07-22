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
#define COLOR_RED     0xF800
#define COLOR_GREEN   0x07E0
#define COLOR_WHITE   0xFFFF
#define COLOR_BLACK   0x0000
#define COLOR_CYAN    0x07FF
#define COLOR_YELLOW  0xFFE0
#define COLOR_GRAY    0x7BEF

// New Vibrant Design Palette Colors
#define COLOR_SKYBLUE 0x03FF
#define COLOR_ORANGE  0xFBE0
#define COLOR_MAGENTA 0xF81F

// Global configuration constants
const uint32_t SAMPLE_RATE = 250000; 
const float US_PER_SAMPLE = 4.0;     

const int N_SAMPLES = 16;
const int N_BUFFERS = 16;

const int TARGET_SAMPLES = 700;
float capturedVoltages[TARGET_SAMPLES];
int totalSamplesCollected = 0;

// System Execution Flags
bool systemActive = false;     
bool isTriggered = false;
bool captureDone = false;
bool ledState = LOW;
unsigned long executionCycleCount = 0;

// Multi-Mode Routing Configuration Engine
enum DataRoute {
  ROUTE_LOCAL_ONLY,
  ROUTE_REMOTE_USB,
  ROUTE_REMOTE_BLE
};
DataRoute currentRoute = ROUTE_LOCAL_ONLY; 
bool bleInitialized = false;

// Reconfigured BLE UART Emulation Profile (Nordic UART standard matching full 128-bit space)
BLEService uartService("6E400001-B5A3-F393-E0A9-E50E24DCCA9E"); 
BLECharacteristic txCharacteristic("6E400003-B5A3-F393-E0A9-E50E24DCCA9E", BLENotify, 20); 

// Non-blocking 200ms touch debounce lockout registers
unsigned long lastTouchTime = 0;
const unsigned long touchLockoutInterval = 200; 

// Non-blocking 1-second automated blink timer registers
unsigned long previousBlinkMillis = 0;
const long blinkInterval = 250; 

// History Rolling Array registers for calculating averages
float fallTimeHistory[10]; 
int totalValidCaptures = 0;
int historyWriteIndex = 0;
float storedBatchAvg10 = -1.0; 

// Side-by-Side Control Geometry Matrix (Clean Spatial Array Layout)
const int btnX = 60;   
const int btnY = 110;   
const int btnW = 320;   
const int btnH = 80;

const int txBtnX = 420;
const int txBtnY = 110;
const int txBtnW = 320;
const int txBtnH = 80;

// --- HARDWARE REGISTER OVERRIDE FOR ARDUINO GIGA R1 ---
void optimizeADCSamplingTime() {
  #if defined(ADC1)
    ADC1->SMPR2 &= ~(0x7UL << 15); 
    ADC1->SMPR2 |= (0x4UL << 15);
    Serial.println(">>> REGISTER OPTIMIZATION SUCCESSFUL: ADC1 Channel 15 set to 64.5 cycles.");
  #else
    Serial.println(">>> REGISTER ERROR: Hardware architecture mismatch.");
  #endif
}

// Helper function to draw the UI button state in Landscape
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

// Helper function to cycle and draw our 3 master data routing states side-by-side
void drawTxModeButton() {
  tft.setTextSize(2);
  tft.setTextColor(COLOR_WHITE);
  
  if (currentRoute == ROUTE_LOCAL_ONLY) {
    tft.fillRect(txBtnX, txBtnY, txBtnW, txBtnH, COLOR_SKYBLUE);
    tft.setCursor(txBtnX + 70, txBtnY + 22);
    tft.print("SYSTEM MODE:");
    tft.setCursor(txBtnX + 85, txBtnY + 44);
    tft.print("LOCAL ONLY");
  } 
  else if (currentRoute == ROUTE_REMOTE_USB) {
    tft.fillRect(txBtnX, txBtnY, txBtnW, txBtnH, COLOR_ORANGE);
    tft.setCursor(txBtnX + 70, txBtnY + 22);
    tft.print("REMOTE MODE:");
    tft.setCursor(txBtnX + 75, txBtnY + 44);
    tft.print("USB TX ACTIVE");
  } 
  else if (currentRoute == ROUTE_REMOTE_BLE) {
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

// Helper function to update data metrics on the LCD screen canvas
void updateDisplayMetrics(float peakVolts, float currentFallTimeUs, float batchAvgFallTimeUs) {
  tft.setTextSize(3);
  
  // 1. Clear and Update Peak Voltage Field
  tft.fillRect(100, 265, 600, 35, COLOR_BLACK); 
  tft.setTextColor(COLOR_YELLOW);
  tft.setCursor(100, 265);
  tft.print("Peak Voltage: ");
  if (peakVolts >= 0.0) { 
    tft.print(peakVolts, 3);
    tft.print(" V");
  } else {
    tft.print("---");
  }

  // 2. Clear and Update Current Single Pulse Fall Time Field
  tft.fillRect(100, 315, 600, 35, COLOR_BLACK); 
  tft.setTextColor(COLOR_CYAN);
  tft.setCursor(100, 315);
  tft.print("Fall Time:    ");
  if (currentFallTimeUs > 0.0) { 
    tft.print(currentFallTimeUs, 2);
    tft.print(" us");
  } else if (currentFallTimeUs == -1.0) {
    tft.print("---");
  } else {
    tft.setTextColor(COLOR_RED);
    tft.print("ERROR");
  }

  // 3. Clear and Update Batch Average Fall Time Field
  tft.fillRect(100, 365, 600, 35, COLOR_BLACK); 
  tft.setTextColor(COLOR_WHITE);
  tft.setCursor(100, 365);
  tft.print("Avg (10 Runs):");
  if (batchAvgFallTimeUs > 0.0) { 
    tft.print(batchAvgFallTimeUs, 2);
    tft.print(" us");
  } else {
    tft.print("---");
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

  // Initialize GIGA Display & Native Touch Hardware
  tft.begin();
  tft.setRotation(1); 
  
  if (touch.begin()) {
    Serial.println("Touch controller initialized successfully.");
  } else {
    Serial.println("Error: Touch controller initialization failed.");
  }
  
  tft.fillScreen(COLOR_BLACK);
  
  // Primary Project Title Placement
  tft.setTextSize(4); 
  tft.setTextColor(COLOR_WHITE);
  tft.setCursor(70, 35); 
  tft.print("Photodetector Decay Analyzer");
  
  // Section Header for Local Data Results Panel
  tft.setTextSize(2);
  tft.setTextColor(COLOR_CYAN);
  tft.setCursor(100, 230);
  tft.print("--- LOCAL ACCELERATED METRICS DISPLAY ---");
  
  // Pre-initialize Bluetooth stack to allow safe live switching while system is active
  if (BLE.begin()) {
    BLE.setLocalName("GIGA_WORKSTATION");
    BLE.setDeviceName("GIGA_WORKSTATION");
    BLE.setAppearance(0x0000); 
       
    uartService.addCharacteristic(txCharacteristic);
    BLE.addService(uartService);
       
    BLE.setConnectionInterval(0x000C, 0x0024);
    BLE.advertise();
    bleInitialized = true;
    Serial.println("BLE UART Stack initialized successfully in background.");
  }

  // Render buttons
  drawButton(systemActive);
  drawTxModeButton(); 
  
  updateDisplayMetrics(-1.0, -1.0, -1.0);

  if (!adc0.begin(AN_RESOLUTION_16, SAMPLE_RATE, N_SAMPLES, N_BUFFERS)) {
    Serial.println("CRITICAL ERROR: Advanced ADC setup failed.");
    while (1);
  }

  optimizeADCSamplingTime();
  previousBlinkMillis = millis();
}

void loop() {
  unsigned long currentMillis = millis();

  // Dynamic status bar polling routine for BLE mode updates
  if (currentRoute == ROUTE_REMOTE_BLE && bleInitialized && (currentMillis % 500 == 0)) {
    static bool lastBleConnState = false;
    bool currentBleConnState = BLE.central() && BLE.central().connected();
    if (currentBleConnState != lastBleConnState) {
      lastBleConnState = currentBleConnState;
      drawTxModeButton(); 
    }
  }

  // 1. TOUCH SCREEN ENGINE WITH LIVE SWITCHING CAPABILITY
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

    // Extended padding boundaries configuration
    bool hitVisualButton = (touchX >= (btnX - 5) && touchX <= (btnX + btnW + 5) && touchY >= (btnY - 5) && touchY <= (btnY + btnH - 5));
    bool hitAltButton    = (touchX >= (btnX - 5) && touchX <= (btnX + btnW + 5) && (480 - touchY) >= (btnY - 5) && (480 - touchY) <= (btnY + btnH - 5));

    bool hitTxModeButton = (touchX >= (txBtnX - 5) && touchX <= (txBtnX + txBtnW + 5) && touchY >= (txBtnY - 5) && touchY <= (txBtnY + txBtnH - 5));
    bool hitAltTxMode    = (touchX >= (txBtnX - 5) && touchX <= (txBtnX + txBtnW + 5) && (480 - touchY) >= (txBtnY - 5) && (480 - touchY) <= (txBtnY + txBtnH - 5));

    // CHECK RIGHT SIDE 3-WAY MODE CONTROLLER (UNLOCKED: WORKS LIVE AT ANY TIME)
    if (hitTxModeButton || hitAltTxMode) {
      if (currentMillis - lastTouchTime >= touchLockoutInterval) {
        
        if (currentRoute == ROUTE_LOCAL_ONLY) {
          currentRoute = ROUTE_REMOTE_USB;
          if (systemActive) {
            tft.fillRect(100, 260, 600, 160, COLOR_BLACK); 
            tft.setTextSize(3);
            tft.setTextColor(COLOR_GRAY);
            tft.setCursor(100, 315);
            tft.print("Processing Remotely...");
          }
        } else if (currentRoute == ROUTE_REMOTE_USB) {
          currentRoute = ROUTE_REMOTE_BLE;
          if (systemActive) {
            tft.fillRect(100, 260, 600, 160, COLOR_BLACK); 
            tft.setTextSize(3);
            tft.setTextColor(COLOR_GRAY);
            tft.setCursor(100, 315);
            tft.print("Processing Remotely...");
          }
        } else {
          currentRoute = ROUTE_LOCAL_ONLY;
          if (systemActive) {
            tft.fillRect(100, 260, 600, 160, COLOR_BLACK);
            updateDisplayMetrics(-1.0, -1.0, -1.0);
          }
        }
        
        drawTxModeButton();
        lastTouchTime = currentMillis;
      }
    }

    // CHECK LEFT SIDE START / STOP CONTROL
    if (hitVisualButton || hitAltButton) {
      if (currentMillis - lastTouchTime >= touchLockoutInterval) {
        systemActive = !systemActive;
        drawButton(systemActive);

        if (!systemActive) {
          ledState = LOW;
          digitalWrite(ledPin, ledState);
          isTriggered = false;
          totalSamplesCollected = 0;
          totalValidCaptures = 0;
          historyWriteIndex = 0;
          storedBatchAvg10 = -1.0;
          
          tft.fillRect(100, 260, 600, 160, COLOR_BLACK);
          updateDisplayMetrics(-1.0, -1.0, -1.0); 
          drawTxModeButton(); 
        } else {
          previousBlinkMillis = currentMillis;
          
          if (currentRoute != ROUTE_LOCAL_ONLY) {
            tft.fillRect(100, 260, 600, 160, COLOR_BLACK); 
            tft.setTextSize(3);
            tft.setTextColor(COLOR_GRAY);
            tft.setCursor(100, 315);
            tft.print("Processing Remotely...");
          }
        }
        
        lastTouchTime = currentMillis; 
      }
    }
  }

  // 2. AUTOMATED CONTINUOUS PULSING ENGINE 
  if (systemActive) {
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

    if (systemActive && isTriggered && !captureDone && ledState == LOW) {
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
    } 
    else {
      buf.release();
    }
  }

  // 4. LIVE REGRESSION ANALYSIS PIPELINE WITH MASTER DESTINATION GATING
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

    // --- HARDWARE GATE CRITICAL CONDITION ---
    if (peakStartVoltage >= 1.0) {
      executionCycleCount++;

      // --- LINEAR REGRESSION CORE MATH ---
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
              
              // ================= DATA ROUTING ISOLATION SWITCHES =================
              
              // ROUTE A: REMOTE TRANSMISSION OVER NATIVE USB SERIAL ONLY
              if (currentRoute == ROUTE_REMOTE_USB) {
                Serial.println("\n---BEGIN TRACE DATA---");
                Serial.println("Sample_Index,Time_us,Voltage_V");

                for (int i = regStartIdx; i <= regEndIdx; i++) {
                  if (i < TARGET_SAMPLES) {
                    float sampleTimeUs = (i - regStartIdx) * US_PER_SAMPLE;
                    float sampleVoltage = capturedVoltages[i];
                    
                    Serial.print(i);              Serial.print(",");
                    Serial.print(sampleTimeUs, 1); Serial.print(",");
                    Serial.println(sampleVoltage, 4);
                  }
                }
                Serial.println("---END TRACE DATA---");
                Serial.flush(); 
              }

              // ROUTE B: REMOTE TRANSMISSION SEGMENTED OVER BLUETOOTH BLE UART
              else if (currentRoute == ROUTE_REMOTE_BLE && bleInitialized && BLE.central() && BLE.central().connected()) {
                char bleTxBuffer[45];
                
                txCharacteristic.writeValue("\n---BEGIN TRACE DATA---\n");
                txCharacteristic.writeValue("Sample_Index,Time_us,Voltage_V\n");

                for (int i = regStartIdx; i <= regEndIdx; i++) {
                  if (i < TARGET_SAMPLES) {
                    float sampleTimeUs = (i - regStartIdx) * US_PER_SAMPLE;
                    float sampleVoltage = capturedVoltages[i];
                    
                    int msgLength = snprintf(bleTxBuffer, sizeof(bleTxBuffer), "%d,%.1f,%.4f\n", i, sampleTimeUs, sampleVoltage);
                    
                    int bytesSent = 0;
                    while (bytesSent < msgLength) {
                      int chunkSize = min(20, msgLength - bytesSent);
                      txCharacteristic.writeValue((uint8_t*)&bleTxBuffer[bytesSent], chunkSize);
                      bytesSent += chunkSize;
                      delayMicroseconds(500); 
                    }
                  }
                }
                txCharacteristic.writeValue("---END TRACE DATA---\n");
              }
              
              // ROUTE C: LOCAL PROCESSING AND RENDERING ONLY
              else if (currentRoute == ROUTE_LOCAL_ONLY) {
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

                updateDisplayMetrics(peakStartVoltage, fallTimeRegUs, storedBatchAvg10);
              }
              
              // ===================================================================

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

    // Reset control variables cleanly for next automated pass
    isTriggered = false;
    totalSamplesCollected = 0;
    captureDone = false; 
  }
}
