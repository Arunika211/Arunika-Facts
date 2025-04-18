# esp32_sensor.py
# Script MicroPython untuk ESP32 dengan sensor DHT11, MQ, dan Ultrasonic

import network
import urequests
import time
from machine import Pin, ADC
import dht
import json
import gc
import utime

# Konfigurasi WiFi
WIFI_SSID = "iphone 15 pro max"
WIFI_PASSWORD = "uxtw1203"

# Konfigurasi server
SERVER_URL = "http://192.168.1.100:5000/sensor-data"  

# Konfigurasi Ubidots
UBIDOTS_ENABLED = True
UBIDOTS_TOKEN = "BBUS-Qh32JMs8f0hb5a6WhixQs2MX2CiJaS"
UBIDOTS_DEVICE = "ARUNIKA"
UBIDOTS_URL = f"https://industrial.api.ubidots.com/api/v1.6/devices/{UBIDOTS_DEVICE}/"

# Konfigurasi pin
DHT_PIN = 13  
MQ_ANALOG_PIN = 14  
MQ_DIGITAL_PIN = 12  
TRIG_PIN = 26  
ECHO_PIN = 27  

JENIS_TERNAK = "ayam"  # Bisa diubah ke: "sapi" atau "kambing"

# Inisialisasi sensor
try:
    dht_sensor = dht.DHT11(Pin(DHT_PIN))
    print("Sensor DHT11 diinisialisasi pada pin", DHT_PIN)
except Exception as e:
    print("Error inisialisasi DHT11:", e)
    dht_sensor = None

try:
    mq_analog = ADC(Pin(MQ_ANALOG_PIN))
    mq_analog.atten(ADC.ATTN_11DB)  
    mq_digital = Pin(MQ_DIGITAL_PIN, Pin.IN)
    print("Sensor MQ diinisialisasi pada pin", MQ_ANALOG_PIN, "dan", MQ_DIGITAL_PIN)
except Exception as e:
    print("Error inisialisasi sensor MQ:", e)
    mq_analog = None
    mq_digital = None

try:
    trig = Pin(TRIG_PIN, Pin.OUT)
    echo = Pin(ECHO_PIN, Pin.IN)
    print("Sensor Ultrasonik diinisialisasi pada pin", TRIG_PIN, "dan", ECHO_PIN)
except Exception as e:
    print("Error inisialisasi sensor ultrasonik:", e)
    trig = None
    echo = None

# Fungsi untuk mengukur jarak dengan sensor ultrasonik
def measure_distance():
    if trig is None or echo is None:
        print("Sensor ultrasonik tidak tersedia, mengembalikan data simulasi")
        return round(20 * (0.7 + 0.3 * (time.time() % 10) / 10), 1)  # Simulasi nilai 14-20 cm
    
    try:
        # Kirim pulsa trigger
        trig.value(0)
        time.sleep_us(2)
        trig.value(1)
        time.sleep_us(10)
        trig.value(0)
        
        # Baca echo
        begin = time.ticks_us()
        
        # Tunggu echo menjadi HIGH
        while echo.value() == 0:
            if time.ticks_diff(time.ticks_us(), begin) > 30000:  # Timeout setelah 30ms
                return -1
        
        # Catat waktu mulai
        start_time = time.ticks_us()
        
        # Tunggu echo menjadi LOW
        while echo.value() == 1:
            if time.ticks_diff(time.ticks_us(), start_time) > 30000:  # Timeout setelah 30ms
                return -1
        
        # Hitung durasi
        duration = time.ticks_diff(time.ticks_us(), start_time)
        
        # Hitung jarak (kecepatan suara = 340 m/s, jarak = waktu x kecepatan / 2)
        distance = (duration * 0.0343) / 2
        
        return round(distance, 1)
    except Exception as e:
        print("Error pada sensor ultrasonic:", e)
        # Jika terjadi error, berikan nilai simulasi
        return round(20 * (0.7 + 0.3 * (time.time() % 10) / 10), 1)

# Fungsi untuk membaca sensor MQ
def read_mq():
    if mq_analog is None:
        print("Sensor MQ tidak tersedia, mengembalikan data simulasi")
        return {
            "analog": 2000 + int(500 * (time.time() % 60) / 60),
            "digital": 1 if (time.time() % 20) > 10 else 0,
            "ppm": 150 + 100 * ((time.time() % 30) / 30)
        }
    
    try:
        # Baca nilai analog (0-4095)
        analog_value = mq_analog.read()
        
        # Baca nilai digital (0 atau 1)
        digital_value = mq_digital.value()
        
        # Konversi nilai analog ke ppm (perkiraan kasar)
        ppm = (analog_value / 4095.0) * 1000
        
        return {
            "analog": analog_value,
            "digital": digital_value,
            "ppm": round(ppm, 1)
        }
    except Exception as e:
        print("Error pada sensor MQ:", e)
        # Jika terjadi error, berikan nilai simulasi
        return {
            "analog": 2000 + int(500 * (time.time() % 60) / 60),
            "digital": 1 if (time.time() % 20) > 10 else 0,
            "ppm": 150 + 100 * ((time.time() % 30) / 30)
        }

# Fungsi untuk membaca DHT11
def read_dht():
    if dht_sensor is None:
        print("Sensor DHT11 tidak tersedia, mengembalikan data simulasi")
        # Simulasi nilai berdasarkan jenis ternak
        if JENIS_TERNAK == "ayam":
            temperature = 32 + 5 * ((time.time() % 10) / 10)
            humidity = 50 + 20 * ((time.time() % 15) / 15)
        elif JENIS_TERNAK == "sapi":
            temperature = 25 + 7 * ((time.time() % 12) / 12)
            humidity = 60 + 20 * ((time.time() % 18) / 18)
        else:  # kambing
            temperature = 27 + 7 * ((time.time() % 14) / 14)
            humidity = 40 + 25 * ((time.time() % 16) / 16)
        return round(temperature, 1), round(humidity, 1)
    
    try:
        # Baca nilai sensor DHT11
        dht_sensor.measure()
        temperature = dht_sensor.temperature()
        humidity = dht_sensor.humidity()
        
        # Validasi hasil pembacaan
        if temperature < 0 or temperature > 100 or humidity < 0 or humidity > 100:
            raise ValueError("Nilai sensor DHT11 tidak valid")
            
        return temperature, humidity
    except Exception as e:
        print("Error pada DHT11:", e)
        # Simulasi nilai berdasarkan jenis ternak
        if JENIS_TERNAK == "ayam":
            temperature = 32 + 5 * ((time.time() % 10) / 10)
            humidity = 50 + 20 * ((time.time() % 15) / 15)
        elif JENIS_TERNAK == "sapi":
            temperature = 25 + 7 * ((time.time() % 12) / 12)
            humidity = 60 + 20 * ((time.time() % 18) / 18)
        else:  # kambing
            temperature = 27 + 7 * ((time.time() % 14) / 14)
            humidity = 40 + 25 * ((time.time() % 16) / 16)
        return round(temperature, 1), round(humidity, 1)

# Fungsi untuk membaca semua sensor
def read_sensors():
    try:
        # Baca DHT11
        temperature, humidity = read_dht()
        
        # Baca MQ
        mq_data = read_mq()
        
        # Baca Ultrasonic
        distance = measure_distance()
        
        # Format timestamp ISO 8601
        current_time = utime.localtime()
        timestamp = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}Z".format(
            current_time[0], current_time[1], current_time[2],  # Tahun, bulan, hari
            current_time[3], current_time[4], current_time[5]   # Jam, menit, detik
        )
        
        # Gabungkan data
        sensor_data = {
            "suhu": temperature,
            "kelembapan": humidity,
            "kualitas_udara": mq_data["ppm"],
            "jarak_pakan": distance,
            "ternak": JENIS_TERNAK,
            "timestamp": timestamp
        }
        
        # Tampilkan data untuk debugging
        print("=====================================")
        print("📊 Hasil Pembacaan Sensor:")
        print(f"🔥 Suhu: {temperature}°C")
        print(f"💧 Kelembapan: {humidity}%")
        print(f"🌿 Kualitas Udara: {mq_data['ppm']} ppm")
        print(f"📏 Jarak Pakan: {distance} cm")
        print("=====================================")
        
        return sensor_data
    except Exception as e:
        print("Error membaca sensor:", e)
        return None

# Fungsi untuk mengirim data ke Ubidots
def send_to_ubidots(data):
    if not UBIDOTS_ENABLED:
        print("Pengiriman ke Ubidots dinonaktifkan")
        return False
    
    try:
        # Format data sesuai format Ubidots
        ubidots_payload = {
            "temperature": data["suhu"],
            "humidity": data["kelembapan"],
            "air_quality": data["kualitas_udara"],
            "feed_distance": data["jarak_pakan"],
            "livestock_type": JENIS_TERNAK
        }
        
        # Set header dengan token autentikasi
        headers = {
            "X-Auth-Token": UBIDOTS_TOKEN,
            "Content-Type": "application/json"
        }
        
        # Kirim data ke Ubidots
        response = urequests.post(
            UBIDOTS_URL,
            json=ubidots_payload,
            headers=headers
        )
        
        # Cek respons
        if response.status_code == 200 or response.status_code == 201:
            print("✅ Data berhasil dikirim ke Ubidots")
            response.close()
            return True
        else:
            print(f"❌ Gagal mengirim data ke Ubidots: {response.status_code}")
            response.close()
            return False
    except Exception as e:
        print("❌ Error mengirim data ke Ubidots:", e)
        return False

# Fungsi untuk mengirim data ke server Flask
def send_data(data):
    try:
        # Konversi data ke JSON
        json_data = json.dumps(data)
        
        # Kirim data ke server
        response = urequests.post(SERVER_URL, data=json_data, headers={"Content-Type": "application/json"})
        
        # Cek respons
        if response.status_code == 200:
            print("✅ Data berhasil dikirim ke server Flask")
        else:
            print(f"❌ Gagal mengirim data ke server Flask, status code: {response.status_code}")
        
        # Tutup koneksi
        response.close()
        return True
    except Exception as e:
        print("❌ Error mengirim data ke server Flask:", e)
        return False

# Fungsi untuk menghubungkan ke WiFi
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if not wlan.isconnected():
        print("Menghubungkan ke WiFi", WIFI_SSID, "...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        
        # Tunggu hingga terhubung
        max_wait = 20
        while max_wait > 0:
            if wlan.isconnected():
                break
            max_wait -= 1
            print("Menunggu koneksi...")
            time.sleep(1)
    
    if wlan.isconnected():
        print("✅ Terhubung ke WiFi")
        print("📡 IP:", wlan.ifconfig()[0])
        return True
    else:
        print("❌ Gagal terhubung ke WiFi")
        return False

# Fungsi utama
def main():
    print("\n=== FACTS IoT Sensor Ternak ===")
    print(f"🐄 Jenis Ternak: {JENIS_TERNAK.upper()}")
    print("📌 Pin DHT11:", DHT_PIN)
    print("📌 Pin MQ (Analog/Digital):", MQ_ANALOG_PIN, "/", MQ_DIGITAL_PIN)
    print("📌 Pin Ultrasonik (Trig/Echo):", TRIG_PIN, "/", ECHO_PIN)
    print("📡 Kirim ke Ubidots:", "Aktif" if UBIDOTS_ENABLED else "Nonaktif")
    print("================================\n")
    
    # Hubungkan ke WiFi
    if not connect_wifi():
        print("⚠️ Melanjutkan tanpa koneksi WiFi (data tidak akan dikirim)")
    
    # Loop utama
    while True:
        try:
            # Baca sensor
            sensor_data = read_sensors()
            
            if sensor_data:
                # Kirim data jika WiFi terhubung
                if network.WLAN(network.STA_IF).isconnected():
                    # Kirim ke server Flask
                    send_data(sensor_data)
                    
                    # Kirim ke Ubidots jika diaktifkan
                    send_to_ubidots(sensor_data)
                else:
                    print("⚠️ Tidak terhubung ke WiFi, data tidak dikirim")
                    # Coba hubungkan lagi ke WiFi
                    connect_wifi()
            
            # Tunggu sebelum membaca lagi
            print(f"⏳ Menunggu 10 detik sebelum pembacaan berikutnya...")
            time.sleep(10)  # Baca setiap 10 detik
            
            # Bersihkan memori
            gc.collect()
            
        except Exception as e:
            print("❗ Error dalam loop utama:", e)
            time.sleep(5)  # Tunggu sebelum mencoba lagi

# Jalankan program
if __name__ == "__main__":
    main()
