#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <WiFiClientSecure.h> 

// 1. Cấu hình Wifi
const char* ssid = "123456789";
const char* password = "87654321";

// 2. Cấu hình HiveMQ lấy từ run.py
const char* mqtt_server = "40f1a9b7ef1f4ae9b2855dff153c4fb7.s1.eu.hivemq.cloud";
const int mqtt_port = 8883; // Cổng bảo mật
const char* mqtt_user = "Project3";
const char* mqtt_pass = "Project3";
const char* mqtt_topic = "aegis/fire_alarm";

#define LED_PIN D1

// Sử dụng WiFiClientSecure thay vì WiFiClient thường
WiFiClientSecure espClient;
PubSubClient client(espClient);

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW); 

  // --- QUAN TRỌNG: Bỏ qua kiểm tra chứng chỉ SSL ---
  // Giúp kết nối nhanh và không bị lỗi bộ nhớ trên ESP8266
  espClient.setInsecure(); 

  setup_wifi();
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
}

void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Dang ket noi Wifi: ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWifi Connected!");
}

void callback(char* topic, byte* payload, unsigned int length) {
  String message = "";
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  Serial.print("Nhan tin nhan: ");
  Serial.println(message);

  if (message == "ON") {
    // Đèn ngoài: HIGH là BẬT
    digitalWrite(LED_PIN, HIGH); 
    Serial.println("=> CHAY! BAT DEN (HIGH)");
  } 
  else if (message == "OFF") {
    // Đèn ngoài: LOW là TẮT
    digitalWrite(LED_PIN, LOW); 
    Serial.println("=> AN TOAN. TAT DEN (LOW)");
  }
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Dang ket noi HiveMQ SSL...");
    String clientId = "ESP8266Client-" + String(random(0xffff), HEX);
    
    // Kết nối với User/Pass
    if (client.connect(clientId.c_str(), mqtt_user, mqtt_pass)) {
      Serial.println("Thanh cong!");
      client.subscribe(mqtt_topic);
    } else {
      Serial.print("Loi, rc=");
      Serial.print(client.state());
      Serial.println(" (Thu lai sau 5s)");
      delay(5000);
    }
  }
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();
}