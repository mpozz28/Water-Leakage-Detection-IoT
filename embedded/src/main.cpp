#include <Arduino.h>
#include <DHT.h>
#include <PubSubClient.h>
#include <WiFi.h>

#define DHTPIN A7
#define DHTTYPE DHT11
#define RED A1
#define GREEN A2
#define BLUE A3
#define BUZZER A4
#define BUZZER_2 A5
#define SONAR A0
#define SONAR_DIGITAL D3
#define LIGHT_SPEED 0.0343

#define SUB_TOPIC "emergency"

const char* ssid = "iPhone de Davide";
const char* pass = "jatedisse";
const char* brokerUser = "teensy";
const char* brokerPass = "";
const char* broker = "172.20.10.4";
const char* distanceTopic = "sensors/process_5/distance";
const char* temperatureTopic = "sensors/process_5/temperature";
const char* humidityTopic = "sensors/process_5/humidity";

WiFiClient espClient;
PubSubClient  client(espClient);
long currentTime, lastTime; 
char messages[50];

DHT dht(DHTPIN, DHTTYPE);

int value = 0;
float time_val  = 0;
float distance = 0;
float temperature = 0;
float humidity = 0;
int buzzers = 1;
int last_press = 0;

void setupWiFi(){
  delay(100);
  Serial.print("\nConnecting to");
  Serial.println(ssid);

  WiFi.begin(ssid, pass);
  while (WiFi.status() != WL_CONNECTED){
    delay(100);
    Serial.print("-");
  }

  Serial.print("\nConnected to ");
  Serial.println(ssid);
}

void reconnect(){
  while (!client.connected()){
    Serial.print("\nConnecting to ");
    Serial.println(broker);
    if (client.connect("172.20.10.4", brokerUser, brokerPass)){
        Serial.print("\nConnected");
        client.subscribe(SUB_TOPIC);
    }else{
      Serial.print("\nConnecting");
      delay(5000);
    }
  }
}

void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message arrived [");
  Serial.print(topic);
  Serial.print("] ");
  for (int i=0;i<length;i++) {
    Serial.print((char)payload[i]);
  }
  Serial.println();
  if((char)payload[0] == '1' & buzzers == 1){
    analogWrite(BUZZER_2, 150);
  }
  else{
    analogWrite(BUZZER_2, 0);
  }
}

void setup() {
  Serial.begin(9600);
  setupWiFi();
  client.setServer(broker, 1883);
  client.setCallback(callback);
  
  pinMode(RED, OUTPUT);
  pinMode(GREEN, OUTPUT);
  pinMode(BLUE, OUTPUT);
  pinMode(BUZZER, INPUT);

  pinMode(SONAR_DIGITAL, OUTPUT);
  pinMode(SONAR, INPUT);
  digitalWrite(SONAR_DIGITAL, LOW);

  pinMode(BUZZER_2, OUTPUT);

  dht.begin();

  client.subscribe(SUB_TOPIC);
}

void read_distance(){
  digitalWrite(SONAR_DIGITAL, HIGH);
  delayMicroseconds(10);
  digitalWrite(SONAR_DIGITAL, LOW);

  time_val = pulseIn(SONAR, HIGH);
  if (time_val * LIGHT_SPEED / 2 >= 4.5)
    distance = (time_val * LIGHT_SPEED) / 2;

  Serial.print("Distance: ");
  Serial.println(distance);
}

void read_temperature(){
  temperature = dht.readTemperature();
  if (isnan(temperature)) {
    Serial.println("Failed to read from DHT sensor!");
  }
  else{
    Serial.print("Temperature: ");
    Serial.println(temperature);
  }
}

void read_humidity(){
  humidity = dht.readHumidity();
  if (isnan(humidity)) {
    Serial.println("Failed to read from DHT sensor!");
  }
  else{
    Serial.print("Humidity: ");
    Serial.println(humidity);
  }
}

void logic_distance(){

  if (distance > 7.5) {
    analogWrite(RED, 255);
    analogWrite(GREEN, 0);
  } else {
    analogWrite(RED, 0);
    analogWrite(GREEN, 255);
  }
}

void update_buzzer(){

  if(last_press == LOW && digitalRead(BUZZER) == LOW);
  else if(last_press == LOW && digitalRead(BUZZER) == HIGH){
    last_press = HIGH;
  }
  else if (last_press == HIGH && digitalRead(BUZZER) == LOW) {
    buzzers = !buzzers;
    last_press = LOW;
  }
  else;

}

void read_values(){
  read_temperature();
  read_humidity();
  read_distance();
}

void loop() {
  update_buzzer();
  read_values();
  logic_distance();
  if (!client.connected()){
    reconnect();
  }
  client.loop();
  currentTime = millis();
  if (currentTime - lastTime > 500){
    snprintf(messages, 75, "%f", distance);
    client.publish(distanceTopic, messages);

    snprintf(messages, 75, "%f", temperature);
    client.publish(temperatureTopic, messages);

    snprintf(messages, 75, "%f", humidity);
    client.publish(humidityTopic, messages);
    lastTime = millis();
  }
}
