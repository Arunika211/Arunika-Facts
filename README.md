# FACTS - Farming Activity and Condition Tracking System

FACTS adalah sistem monitoring berbasis IoT untuk memantau kondisi kandang ternak, menggunakan ESP32 sebagai modul IoT dan dashboard berbasis Streamlit.

## Fitur Utama

- 📊 Dashboard monitoring real-time untuk suhu, kelembapan, kualitas udara, dan jarak pakan
- 🎥 Deteksi aktivitas ternak dengan YOLO (You Only Look Once)
- 🤖 Analisis AI menggunakan Gemini untuk memberikan rekomendasi pengelolaan ternak
- 📱 Pengiriman data ke platform Ubidots untuk akses data jarak jauh
- 🔄 Simulasi sensor untuk keperluan pengujian
- 💾 Penyimpanan data ke MongoDB dan JSON lokal

## Instalasi

### Persyaratan Sistem

- Python 3.8 atau lebih baru
- ESP32 dengan MicroPython (untuk deployment perangkat sebenarnya)
- Webcam (untuk fitur deteksi)
- Akses MongoDB (opsional, untuk penyimpanan data)

### Instalasi Dependensi

1. Clone repositori ini
```bash
git clone https://github.com/username/facts-monitoring.git
cd facts-monitoring
```

2. Instal semua dependensi
```bash
pip install -r requirements.txt
```

### Konfigurasi

1. Konfigurasikan server Flask dan MongoDB dalam file `config.ini`
```ini
[SERVER]
host = 0.0.0.0
port = 5000
debug = True

[DATA]
max_entries = 1000

[DATABASE]
mongodb_uri = mongodb+srv://username:password@cluster.mongodb.net/
db_name = HasilKoleksi  
sensor_collection = sensor_data
cv_collection = cv_activity
```

2. Untuk konfigurasi Ubidots, sesuaikan token dan nama device di `sensor.py`

## Penggunaan

### Menjalankan Server

```bash
python server.py
```

### Menjalankan Dashboard

```bash
streamlit run dashboard.py
```

### Pengujian dan Deployment

FACTS menggunakan dua file utama untuk pengiriman data sensor:

#### 1. `send-sensor.py` - UNTUK PENGUJIAN KONEKSI

File ini digunakan KHUSUS untuk pengujian koneksi pada PC/laptop, tidak untuk deployment. 
Gunakan untuk memverifikasi koneksi ke server Flask, MongoDB, dan Ubidots sebelum melakukan deployment ke ESP32.

```bash
# Pengujian dasar:
python send-sensor.py --ternak ayam --interval 5

# Pengujian dengan MongoDB:
python send-sensor.py --ternak sapi --mongodb "mongodb+srv://username:password@cluster.mongodb.net/"
```

Parameter tersedia:
- `--ternak`: Jenis ternak (ayam, sapi, kambing)
- `--flask-url`: URL endpoint Flask
- `--ubidots-token`: Token autentikasi Ubidots
- `--ubidots-device`: Nama device di Ubidots
- `--interval`: Interval pengiriman data dalam detik
- `--mongodb`: URI MongoDB (opsional)

#### 2. `sensor.py` - UNTUK DEPLOYMENT ESP32

File ini adalah **script utama MicroPython** yang digunakan pada ESP32 yang terhubung dengan sensor fisik.
File ini **tidak menggunakan MongoDB**, hanya mengirim data ke server Flask dan Ubidots.

```bash
# Unggah ke ESP32 menggunakan Thonny IDE atau esptool
```

## Struktur Proyek

- `dashboard.py`: Dashboard Streamlit untuk monitoring data
- `server.py`: Server Flask untuk menerima dan menyimpan data
- `sensor.py`: **Script utama MicroPython untuk ESP32** (deployment)
- `send-sensor.py`: Script Python untuk pengujian koneksi di PC (testing)
- `requirements.txt`: Daftar dependensi Python
- `data/`: Direktori penyimpanan data JSON
- `config.ini`: File konfigurasi server dan MongoDB

## Integrasi dengan ESP32

Pastikan ESP32 Anda telah terinstal MicroPython. Sensor yang didukung:

- DHT11 pada pin 13 untuk suhu dan kelembapan
- MQ sensor pada pin analog 14 dan digital 12 untuk kualitas udara
- Sensor ultrasonik dengan pin trigger 26 dan echo 27 untuk jarak pakan

Untuk mengunggah `sensor.py` ke ESP32:
1. Instal Thonny IDE
2. Hubungkan ESP32 ke komputer
3. Pilih interpreter MicroPython
4. Buka file `sensor.py` dan sesuaikan konfigurasi (terutama WIFI_SSID dan WIFI_PASSWORD)
5. Unggah ke ESP32 dengan klik "Upload to /")

## Integrasi dengan MongoDB

Data sensor dan aktivitas CV dapat disimpan ke MongoDB:

1. Buat akun di [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
2. Buat cluster dan database
3. Dapatkan URI koneksi MongoDB
4. Konfigurasi di `config.ini` pada bagian `[DATABASE]` (atau `[MONGO]`)
   ```ini
   [DATABASE]
   mongodb_uri = mongodb+srv://username:password@cluster.mongodb.net/
   db_name = HasilKoleksi  
   sensor_collection = sensor_data
   cv_collection = cv_activity
   ```

   Atau alternatif format:
   ```ini
   [MONGO]
   enabled = true
   uri = mongodb+srv://username:password@cluster.mongodb.net/
   db = facts_data
   sensor_collection = sensor_data
   cv_collection = cv_activity
   ```

Kedua format konfigurasi di atas didukung oleh sistem. `server.py` dan `send-sensor.py` secara otomatis akan mencari konfigurasi di kedua bagian.

## Integrasi dengan Ubidots

Data sensor juga dikirim ke platform Ubidots untuk visualisasi dan analisis jarak jauh:

1. Buat akun di [Ubidots](https://ubidots.com/)
2. Dapatkan token API Anda
3. Sesuaikan token dan nama device di script `sensor.py`
4. Buat dashboard di Ubidots untuk memvisualisasikan data

## Perintah-perintah Penting

- **Menjalankan server**: `python server.py`
- **Menjalankan dashboard**: `streamlit run dashboard.py`
- **Pengujian koneksi**: `python send-sensor.py --ternak ayam`
- **Mengecek data**: Buka `http://localhost:8501` untuk melihat dashboard Streamlit

## Pemecahan Masalah

- Pastikan server Flask berjalan sebelum menjalankan simulator atau dashboard
- Periksa kredensial WiFi dan endpoint server di script `sensor.py` untuk ESP32
- Periksa port kamera di dashboard jika fitur deteksi tidak berfungsi
- Verifikasi URI MongoDB Anda jika menggunakan penyimpanan MongoDB
- **Pengguna Windows**: Jika mengalami masalah koneksi seperti `WinError 10049`, pastikan konfigurasi host di `config.ini` menggunakan `localhost` atau `127.0.0.1` dan bukan `0.0.0.0`

## Catatan Penting

- Script telah dioptimalkan untuk menggunakan parameter `use_container_width=True` sebagai pengganti `use_column_width` yang sudah tidak digunakan lagi di Streamlit terbaru.
- ESP32 hanya menggunakan `sensor.py`, sedangkan `send-sensor.py` digunakan untuk pengujian pada PC.
- Pastikan untuk memeriksa dokumentasi terbaru pada [Streamlit](https://docs.streamlit.io/) jika terjadi perubahan API.

## Kontributor

- [Nama Anda] (https://github.com/username) 