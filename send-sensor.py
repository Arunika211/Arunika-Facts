#!/usr/bin/env python3
# send-sensor.py
# Script untuk mengirim data sensor random ke Flask dan Ubidots <Test Case Only>

import requests
import time
import random
import argparse
import json
import os
import configparser
from datetime import datetime
from pymongo import MongoClient
import platform

# Coba membaca konfigurasi dari file config.ini jika ada
config = configparser.ConfigParser()
try:
    if os.path.exists('config.ini'):
        config.read('config.ini')
        print("✅ Berhasil membaca konfigurasi dari config.ini")
    else:
        print("⚠️ File config.ini tidak ditemukan, menggunakan nilai default")
except Exception as e:
    print(f"❌ Error membaca konfigurasi: {e}")

# Tentukan host default berdasarkan OS
# Di Windows, gunakan 'localhost' atau '127.0.0.1' untuk menghindari error koneksi
is_windows = platform.system().lower() == 'windows'
default_host = 'localhost' if is_windows else config.get('SERVER', 'host', fallback='0.0.0.0')
default_port = config.get('SERVER', 'port', fallback='5000')

# Parsing argumen untuk memilih jenis ternak
parser = argparse.ArgumentParser(description='Simulator untuk data sensor ternak')
parser.add_argument('--ternak', type=str, default='ayam', choices=['ayam', 'sapi', 'kambing'],
                    help='Jenis ternak (ayam, sapi, kambing)')
                    
# Default Flask URL dari config.ini atau nilai default
default_flask_url = f"http://{default_host}:{default_port}/sensor-data"
parser.add_argument('--flask-url', type=str, default=default_flask_url,
                    help='URL endpoint Flask')
                    
parser.add_argument('--ubidots-token', type=str, default='BBUS-Qh32JMs8f0hb5a6WhixQs2MX2CiJaS',
                    help='Token autentikasi Ubidots')
parser.add_argument('--ubidots-device', type=str, default='ARUNIKA',
                    help='Nama device di Ubidots')
parser.add_argument('--interval', type=int, default=10,
                    help='Interval pengiriman data dalam detik')

# Default MongoDB dari config.ini
default_mongodb_uri = config.get('DATABASE', 'mongodb_uri', fallback=None) if 'DATABASE' in config else \
                      config.get('MONGO', 'uri', fallback=None) if 'MONGO' in config else None
                      
default_mongodb_db = config.get('DATABASE', 'db_name', fallback='facts_data') if 'DATABASE' in config else \
                     config.get('MONGO', 'db', fallback='facts_data') if 'MONGO' in config else 'facts_data'
                     
default_mongodb_collection = config.get('DATABASE', 'sensor_collection', fallback='sensor_data') if 'DATABASE' in config else \
                             config.get('MONGO', 'sensor_collection', fallback='sensor_data') if 'MONGO' in config else 'sensor_data'

parser.add_argument('--mongodb', type=str, default=default_mongodb_uri,
                    help='URI MongoDB, jika diisi maka data akan dikirim ke MongoDB')
parser.add_argument('--mongodb-db', type=str, default=default_mongodb_db,
                    help='Nama database MongoDB')
parser.add_argument('--mongodb-collection', type=str, default=default_mongodb_collection,
                    help='Nama collection MongoDB')
args = parser.parse_args()

# Konfigurasi endpoint
FLASK_URL = args.flask_url
UBIDOTS_TOKEN = args.ubidots_token
UBIDOTS_DEVICE = args.ubidots_device
UBIDOTS_URL = f"https://industrial.api.ubidots.com/api/v1.6/devices/{UBIDOTS_DEVICE}/"
JENIS_TERNAK = args.ternak
INTERVAL = args.interval

# Konfigurasi MongoDB
MONGODB_ENABLED = args.mongodb is not None
MONGODB_URI = args.mongodb
MONGODB_DB = args.mongodb_db
MONGODB_COLLECTION = args.mongodb_collection
mongo_client = None
mongo_collection = None

# Inisialisasi koneksi MongoDB jika diaktifkan
if MONGODB_ENABLED:
    try:
        mongo_client = MongoClient(MONGODB_URI)
        # Tes koneksi
        mongo_client.admin.command('ping')
        mongo_db = mongo_client[MONGODB_DB]
        mongo_collection = mongo_db[MONGODB_COLLECTION]
        print(f"✅ Berhasil terhubung ke MongoDB: {MONGODB_URI}")
        print(f"✅ Database: {MONGODB_DB}, Collection: {MONGODB_COLLECTION}")
    except Exception as e:
        print(f"❌ Error saat koneksi ke MongoDB: {e}")
        MONGODB_ENABLED = False

def generate_dummy_data(jenis_ternak):
    # Range nilai sensor disesuaikan berdasarkan jenis ternak
    if jenis_ternak == "ayam":
        suhu = round(random.uniform(32.0, 37.0), 1)  # Ayam butuh suhu lebih tinggi
        kelembapan = round(random.uniform(50.0, 70.0), 1)
    elif jenis_ternak == "sapi":
        suhu = round(random.uniform(25.0, 32.0), 1)  # Sapi butuh suhu lebih rendah
        kelembapan = round(random.uniform(60.0, 80.0), 1)
    else:  # kambing
        suhu = round(random.uniform(27.0, 34.0), 1)
        kelembapan = round(random.uniform(40.0, 65.0), 1)
    
    kualitas_udara = round(random.uniform(50, 400), 2)  # ppm
    jarak_pakan = round(random.uniform(2.0, 20.0), 1)  # cm

    # Pastikan format timestamp konsisten (ISO 8601 dengan timezone info)
    current_time = datetime.now()
    timestamp = current_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    return {
        "suhu": suhu,
        "kelembapan": kelembapan,
        "kualitas_udara": kualitas_udara,
        "jarak_pakan": jarak_pakan,
        "ternak": jenis_ternak,
        "timestamp": timestamp
    }

def send_to_flask(data):
    try:
        # Kirim data ke server Flask
        response = requests.post(FLASK_URL, json=data)
        
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

def send_to_ubidots(data):
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
        response = requests.post(
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
    
def save_to_mongodb(data):
    if not MONGODB_ENABLED or mongo_collection is None:
        return False
    
    try:
        # Konversi timestamp string ke objek datetime untuk MongoDB
        if "timestamp" in data and isinstance(data["timestamp"], str):
            try:
                data["timestamp"] = datetime.fromisoformat(data["timestamp"])
            except ValueError:
                # Jika format tidak valid, biarkan sebagai string
                pass
        
        # Simpan ke MongoDB
        result = mongo_collection.insert_one(data)
        print(f"✅ Data berhasil disimpan ke MongoDB (ID: {result.inserted_id})")
        return True
    except Exception as e:
        print(f"❌ Error menyimpan data ke MongoDB: {e}")
        return False

def main():
    print("\n=== FACTS IoT Sensor Simulator ===")
    print(f"🐄 Jenis Ternak: {JENIS_TERNAK.upper()}")
    print(f"📡 Flask URL: {FLASK_URL}")
    print(f"📡 Ubidots Device: {UBIDOTS_DEVICE}")
    print(f"⏱️ Interval: {INTERVAL} detik")
    if MONGODB_ENABLED:
        print(f"🗄️ MongoDB: {MONGODB_URI}")
        print(f"🗄️ Database: {MONGODB_DB}")
        print(f"🗄️ Collection: {MONGODB_COLLECTION}")
    print("================================\n")
    
    # Loop utama
    while True:
        try:
            # Generate data random
            sensor_data = generate_dummy_data(JENIS_TERNAK)
            
            # Tampilkan data untuk debugging
            print("=====================================")
            print("📊 Data yang akan dikirim:")
            print(f"🔥 Suhu: {sensor_data['suhu']}°C")
            print(f"💧 Kelembapan: {sensor_data['kelembapan']}%")
            print(f"🌿 Kualitas Udara: {sensor_data['kualitas_udara']} ppm")
            print(f"📏 Jarak Pakan: {sensor_data['jarak_pakan']} cm")
            print("=====================================")
            
            # Kirim ke server Flask
            send_to_flask(sensor_data)
            
            # Kirim ke Ubidots
            send_to_ubidots(sensor_data)
            
            # Simpan ke MongoDB jika diaktifkan
            if MONGODB_ENABLED:
                save_to_mongodb(sensor_data)
            
            # Tunggu sebelum mengirim lagi
            print(f"⏳ Menunggu {INTERVAL} detik sebelum pengiriman berikutnya...")
            time.sleep(INTERVAL)
            
        except Exception as e:
            print("❗ Error dalam loop utama:", e)
            time.sleep(5)  # Tunggu sebelum mencoba lagi

# Jalankan program
if __name__ == "__main__":
    main() 