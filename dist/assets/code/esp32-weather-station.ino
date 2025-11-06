#include <Wire.h>
#include <U8g2lib.h>
#include <DHT.h>

// ===== CONFIGURAZIONE =====
#define OLED_ADDR 0x3C
#define I2C_SDA   21
#define I2C_SCL   22

#define DHTPIN    4
#define DHTTYPE   DHT11

U8G2_SH1106_128X64_NONAME_F_HW_I2C u8g2(U8G2_R0, /*reset=*/ U8X8_PIN_NONE);
DHT dht(DHTPIN, DHTTYPE);

// --- smoothing su 5 campioni ---
const int N = 5;
float bufT[N] = {NAN}, bufH[N] = {NAN};
int idx = 0;

float avg(float *b) {
  float s = 0; int c = 0;
  for (int i=0; i<N; i++) if(!isnan(b[i])) { s += b[i]; c++; }
  return (c>0)? s/c : NAN;
}

// --- Disegna una schermata completa ---
void drawBigValue(float val, const char* unit, bool drawDegree, const char* title) {
  u8g2.clearBuffer();

  // Titolo in alto
  u8g2.setFont(u8g2_font_6x12_tf);
  int wTitle = u8g2.getStrWidth(title);
  u8g2.drawStr((128 - wTitle) / 2, 10, title);  // centrato orizzontalmente

  // Valore grande
  char strVal[10];
  if (strcmp(unit, "%") == 0)
    snprintf(strVal, sizeof(strVal), "%.0f", val);
  else
    snprintf(strVal, sizeof(strVal), "%.1f", val);

  u8g2.setFont(u8g2_font_logisoso42_tf);
  int wNum = u8g2.getStrWidth(strVal);
  int xNum = (128 - wNum) / 2;
  int yBase = 58;
  u8g2.drawStr(xNum, yBase, strVal);

  // Disegna unità (°C o %)
  u8g2.setFont(u8g2_font_6x12_tf);
  int xUnit = xNum + wNum + 4;
  if (drawDegree) {
    u8g2.drawStr(xUnit, yBase - 22, "o");
    xUnit += 8;
  }
  u8g2.drawStr(xUnit, yBase, unit);

  u8g2.sendBuffer();
}

// --- LOOP PRINCIPALE ---
unsigned long lastRead = 0;
unsigned long lastSwitch = 0;
bool showTemp = true;

void setup() {
  Serial.begin(115200);
  Wire.begin(I2C_SDA, I2C_SCL);
  u8g2.setI2CAddress(OLED_ADDR << 1);
  u8g2.begin();
  dht.begin();
}

void loop() {
  unsigned long now = millis();

  // Lettura sensore ogni 2 s
  if (now - lastRead >= 2000) {
    lastRead = now;
    float h = dht.readHumidity();
    float t = dht.readTemperature();

    if (!isnan(h) && !isnan(t)) {
      bufT[idx] = t;
      bufH[idx] = h;
      idx = (idx + 1) % N;
    } else {
      Serial.println("Errore DHT");
    }
  }

  // Cambio schermata ogni 3 secondi
  if (now - lastSwitch >= 5000) {
    lastSwitch = now;
    showTemp = !showTemp;
  }

  // Mostra schermata corrente
  if (showTemp)
    drawBigValue(avg(bufT), "C", true, "Temperature");
  else
    drawBigValue(avg(bufH), "%", false, "Humidity");

  delay(100);
}
