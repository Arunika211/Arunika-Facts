import streamlit as st
import pandas as pd
import json
from google import genai
from ultralytics import YOLO
import cv2
import os
import requests
import time
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import numpy as np
import configparser
from pymongo import MongoClient
import traceback

# Konfigurasi halaman
st.set_page_config(
    page_title="FACTS Monitoring Dashboard",
    page_icon="🐄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Konfigurasi untuk API dan endpoints dari secrets.toml
# Fallback ke nilai default jika secrets tidak tersedia
if "api" in st.secrets:
    flask_host = st.secrets["server"]["flask_host"]
    flask_port = st.secrets["server"]["flask_port"]
    gemini_api_key = st.secrets["api"]["gemini_api_key"]
    model_paths = {
        "ayam": st.secrets["models"]["ayam"],
        "sapi": st.secrets["models"]["sapi"],
        "kambing": st.secrets["models"]["kambing"]
    }
else:
    # Fallback ke nilai default jika secrets tidak tersedia
    flask_host = "localhost"
    flask_port = "5000"
    gemini_api_key = "AIzaSyDzDgcINn520vBVCwDdzl4HHWrUyZAa08A"
    model_paths = {
        "ayam": "models/ayam.pt",
        "sapi": "models/sapi.pt",
        "kambing": "models/kambing.pt"
    }

# URL Flask API dari konfigurasi
API_URL_SENSOR = f"http://{flask_host}:{flask_port}/sensor-data"
API_URL_CV = f"http://{flask_host}:{flask_port}/cv-activity"

# Konfigurasi MongoDB
config = configparser.ConfigParser()
try:
    if os.path.exists('config.ini'):
        config.read('config.ini')
        
        # Cek apakah MongoDB diaktifkan dalam konfigurasi
        MONGO_ENABLED = config.getboolean('MONGO', 'enabled', fallback=False) if 'MONGO' in config else \
                        config.getboolean('DATABASE', 'enabled', fallback=True) if 'DATABASE' in config else False
                        
        # Dapatkan konfigurasi MongoDB
        MONGO_URI = config.get('MONGO', 'uri', fallback=None) if 'MONGO' in config else \
                    config.get('DATABASE', 'mongodb_uri', fallback=None) if 'DATABASE' in config else None
                    
        MONGO_DB = config.get('MONGO', 'db', fallback="HasilKoleksi") if 'MONGO' in config else \
                   config.get('DATABASE', 'db_name', fallback="HasilKoleksi") if 'DATABASE' in config else "HasilKoleksi"
                   
        MONGO_SENSOR_COLLECTION = config.get('MONGO', 'sensor_collection', fallback="sensor_data") if 'MONGO' in config else \
                                  config.get('DATABASE', 'sensor_collection', fallback="sensor_data") if 'DATABASE' in config else "sensor_data"
                                  
        MONGO_CV_COLLECTION = config.get('MONGO', 'cv_collection', fallback="cv_activity") if 'MONGO' in config else \
                              config.get('DATABASE', 'cv_collection', fallback="cv_activity") if 'DATABASE' in config else "cv_activity"
    else:
        MONGO_ENABLED = False
        MONGO_URI = None
except Exception as e:
    print(f"Error membaca konfigurasi: {e}")
    MONGO_ENABLED = False
    MONGO_URI = None

# Inisialisasi koneksi MongoDB
mongo_client = None
mongo_db = None
mongo_sensor_collection = None
mongo_cv_collection = None

if MONGO_ENABLED and MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI)
        # Cek koneksi
        mongo_client.admin.command('ping')
        mongo_db = mongo_client[MONGO_DB]
        mongo_sensor_collection = mongo_db[MONGO_SENSOR_COLLECTION]
        mongo_cv_collection = mongo_db[MONGO_CV_COLLECTION]
    except Exception as e:
        print(f"Gagal terhubung ke MongoDB: {str(e)}")
        MONGO_ENABLED = False

# Inisialisasi session_state untuk tracking deteksi
if "detection_running" not in st.session_state:
    st.session_state.detection_running = False
if "camera_stream" not in st.session_state:
    st.session_state.camera_stream = None
if "detection_counter" not in st.session_state:
    st.session_state.detection_counter = 0
if "detection_confidence" not in st.session_state:
    st.session_state.detection_confidence = []
if "detection_times" not in st.session_state:
    st.session_state.detection_times = []

# Deteksi tema Streamlit yang sedang digunakan
# Tema default adalah 'light', dan bisa diubah oleh pengguna melalui pengaturan Streamlit
dark_mode = False
try:
    # Coba deteksi tema dengan mengevaluasi tema dari CSS
    dark_mode = st.config.get_option("theme.base") == "dark"
    
    # Juga cek beberapa properti CSS untuk konfirmasi
    theme_txt_color = st.config.get_option("theme.textColor")
    if theme_txt_color and (theme_txt_color.startswith("#f") or theme_txt_color.startswith("#e")):
        dark_mode = True
except:
    # Fallback: Coba cara lain untuk mendeteksi dark mode
    try:
        # Ini metode alternatif untuk mendeteksi dark mode
        import streamlit as _st
        from streamlit.commands.page_config import get_option
        dark_mode = get_option("theme.base") == "dark"
    except:
        # Kalau gagal sepenuhnya, default ke light mode
        dark_mode = False
        
# Memastikan tema diaplikasikan dengan benar
st.markdown(f'''
    <script>
        // Mendeteksi tema browser untuk fallback
        const darkModePreference = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        
        // Set dark theme jika diperlukan
        if ({'true' if dark_mode else 'false'} || darkModePreference) {{
            // Force dark mode
            document.body.classList.add('dark');
            document.querySelector('body').style.backgroundColor = '#0e1117';
            document.querySelector('body').style.color = '#fafafa';
        }}
        
        // Tambahkan listener untuk perubahan tema
        const observer = new MutationObserver((mutations) => {{
            // Jika tema berubah, refresh halaman
            window.location.reload();
        }});
        
        // Observe perubahan pada body class (tanda tema berubah)
        observer.observe(document.body, {{ attributes: true, attributeFilter: ['class'] }});
    </script>
''', unsafe_allow_html=True)

# Warna berdasarkan tema
if dark_mode:
    # Tema gelap
    primary_color = "#4da6ff"
    secondary_color = "#0c4da2"
    text_color = "#e0e0e0"
    card_bg = "#2c3e50"
    bg_color = "#1e1e1e"
    success_color = "#00cc66"
    warning_color = "#ff9933"
    error_color = "#ff5050"
    metric_bg = "#283747"
    border_color = "#4e5d6c"
else:
    # Tema terang
    primary_color = "#3366ff"
    secondary_color = "#0c4da2"
    text_color = "#333333"
    card_bg = "#ffffff"
    bg_color = "#f8f9fa"
    success_color = "#28a745"
    warning_color = "#ffc107"
    error_color = "#dc3545"
    metric_bg = "#f8f9fa"
    border_color = "#e9ecef"

# CSS kustom yang responsif terhadap tema
st.markdown(f"""
<style>
    .main-header {{
        font-size: 2.5rem;
        color: {primary_color};
        text-align: center;
        margin-bottom: 1rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }}
    .sub-header {{
        font-size: 1.8rem;
        color: {secondary_color};
        margin-bottom: 0.8rem;
        border-bottom: 2px solid {border_color};
        padding-bottom: 0.5rem;
    }}
    .metric-container {{
        background-color: {metric_bg};
        border-radius: 10px;
        padding: 1rem;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
        border: 1px solid {border_color};
    }}
    .metric-value {{
        font-size: 2.2rem;
        font-weight: bold;
        color: {secondary_color};
    }}
    .metric-label {{
        font-size: 1rem;
        color: {text_color};
        opacity: 0.8;
    }}
    .trend-up {{
        color: {success_color};
    }}
    .trend-down {{
        color: {error_color};
    }}
    .card {{
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        background-color: {card_bg};
        border: 1px solid {border_color};
    }}
    .sidebar .stButton>button {{
        width: 100%;
        margin-bottom: 0.5rem;
    }}
    .status-indicator {{
        width: 12px;
        height: 12px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 5px;
    }}
    .status-active {{
        background-color: {success_color};
    }}
    .status-inactive {{
        background-color: {error_color};
    }}
    .status-text {{
        display: inline-block;
        vertical-align: middle;
    }}
    .theme-info {{
        text-align: center;
        font-size: 0.8rem;
        color: {text_color};
        opacity: 0.7;
        margin-top: 1rem;
    }}
    .footer {{
        text-align: center;
        color: {text_color};
        opacity: 0.7;
        padding: 1rem;
        border-top: 1px solid {border_color};
        margin-top: 2rem;
    }}
    .warning-text {{
        color: {warning_color};
    }}
    .success-text {{
        color: {success_color};
    }}
    .error-text {{
        color: {error_color};
    }}
    .info-card {{
        background-color: {bg_color};
        border-left: 5px solid {primary_color};
        padding: 1rem;
        margin-bottom: 1rem;
    }}
</style>

<!-- Auto-refresh script -->
<script>
    // Auto-refresh setiap 60 detik
    setTimeout(function(){{
        window.location.reload();
    }}, 60000);
</script>
""", unsafe_allow_html=True)

# Path absolut untuk file data
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SENSOR_FILE = os.path.join(DATA_DIR, "sensor_data.json")
CV_FILE = os.path.join(DATA_DIR, "cv_activity.json")

# Pastikan direktori data ada
os.makedirs(DATA_DIR, exist_ok=True)

# API key Gemini dari konfigurasi
API_GEMINI = gemini_api_key

# Model paths dari konfigurasi
MODEL_PATHS = model_paths

# Setup sidebar
st.sidebar.markdown(f"<h2 style='text-align: center; color: {primary_color};'>🐄 FACTS Control</h2>", unsafe_allow_html=True)
st.sidebar.markdown("---")

# Tampilkan info tentang tema saat ini
st.sidebar.markdown(f"<div class='theme-info'>Tema Saat Ini: {'Gelap' if dark_mode else 'Terang'}</div>", unsafe_allow_html=True)
st.sidebar.markdown("<div class='theme-info'>Ubah tema di menu Pengaturan ⚙️</div>", unsafe_allow_html=True)
st.sidebar.markdown("---")

# Sidebar - Bagian Kontrol Kamera
st.sidebar.markdown(f"<h3 style='color: {secondary_color};'>🎥 Kontrol Kamera</h3>", unsafe_allow_html=True)

# Status indikator untuk kamera
camera_active = st.sidebar.toggle("Aktifkan Kamera", value=False)
if camera_active:
    st.sidebar.markdown("""
    <div>
        <span class="status-indicator status-active"></span>
        <span class="status-text">Kamera Aktif</span>
    </div>
    """, unsafe_allow_html=True)
else:
    st.sidebar.markdown("""
    <div>
        <span class="status-indicator status-inactive"></span>
        <span class="status-text">Kamera Nonaktif</span>
    </div>
    """, unsafe_allow_html=True)

camera_type = st.sidebar.radio("Pilih Sumber Kamera", ["Webcam", "Upload Video"], disabled=not camera_active)

# Pilihan model ternak dengan ikon
st.sidebar.markdown(f"<h3 style='color: {secondary_color};'>🐔 Pilih Jenis Ternak</h3>", unsafe_allow_html=True)
ternak_options = ["ayam", "sapi", "kambing"]
ternak_icons = {"ayam": "🐔", "sapi": "🐄", "kambing": "🐐"}

selected_ternak = st.sidebar.selectbox(
    "Jenis Ternak", 
    ternak_options, 
    format_func=lambda x: f"{ternak_icons[x]} {x.capitalize()}"
)

# Tombol kontrol dengan warna dan ikon
col1, col2 = st.sidebar.columns(2)
with col1:
    start_detection = st.button(
        "▶️ Mulai Deteksi", 
        disabled=not camera_active,
        type="primary"
    )
with col2:
    stop_detection = st.button(
        "⏹️ Hentikan", 
        disabled=not camera_active,
        type="secondary"
    )

# Informasi status server dan tombol tes di bagian bawah sidebar
st.sidebar.markdown("---")
st.sidebar.markdown(f"<h3 style='color: {secondary_color};'>📊 Status Sistem</h3>", unsafe_allow_html=True)

# Menghitung jumlah data yang ada (untuk informasi)
def count_data():
    sensor_count = 0
    cv_count = 0
    try:
        if os.path.exists(SENSOR_FILE):
            with open(SENSOR_FILE, "r") as f:
                sensor_data = json.load(f)
                sensor_count = len(sensor_data)
        if os.path.exists(CV_FILE):
            with open(CV_FILE, "r") as f:
                cv_data = json.load(f)
                cv_count = len(cv_data)
    except:
        pass
    return sensor_count, cv_count

sensor_count, cv_count = count_data()

# Menampilkan info data dalam bentuk metrik yang menarik
col1, col2 = st.sidebar.columns(2)
with col1:
    st.markdown(f"""
    <div class="metric-container" style="text-align: center;">
        <div class="metric-value">{sensor_count}</div>
        <div class="metric-label">Data Sensor</div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
    <div class="metric-container" style="text-align: center;">
        <div class="metric-value">{cv_count}</div>
        <div class="metric-label">Data Aktivitas</div>
    </div>
    """, unsafe_allow_html=True)

# Tombol untuk mengetes koneksi dengan ikon
if st.sidebar.button("🛠️ Tes Koneksi & Kirim Data", type="primary"):
    with st.sidebar.status("Menjalankan tes koneksi..."):
        try:
            # Uji koneksi ke server
            response = requests.get("http://localhost:5000/")
            if response.status_code == 200:
                st.sidebar.markdown(f"<div class='success-text'>✅ Server berjalan: {response.text}</div>", unsafe_allow_html=True)
                
                # Kirim data uji
                test_data = {
                    "suhu": 36.5, 
                    "kelembapan": 70.0,
                    "kualitas_udara": 150.0,
                    "ternak": selected_ternak,
                    "test": True
                }
                
                response = requests.post(API_URL_SENSOR, json=test_data)
                if response.status_code == 200:
                    st.sidebar.markdown("<div class='success-text'>✅ Data uji berhasil dikirim!</div>", unsafe_allow_html=True)
                    # Update jumlah data yang ada
                    sensor_count, cv_count = count_data()
                    # Refresh metrik
                    col1, col2 = st.sidebar.columns(2)
                    with col1:
                        st.markdown(f"""
                        <div class="metric-container" style="text-align: center;">
                            <div class="metric-value">{sensor_count}</div>
                            <div class="metric-label">Data Sensor</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with col2:
                        st.markdown(f"""
                        <div class="metric-container" style="text-align: center;">
                            <div class="metric-value">{cv_count}</div>
                            <div class="metric-label">Data Aktivitas</div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.sidebar.markdown(f"<div class='error-text'>❌ Gagal mengirim data: {response.status_code}</div>", unsafe_allow_html=True)
            else:
                st.sidebar.markdown(f"<div class='error-text'>❌ Server merespons dengan kode: {response.status_code}</div>", unsafe_allow_html=True)
        except requests.exceptions.ConnectionError:
            st.sidebar.markdown("<div class='error-text'>❌ Tidak dapat terhubung ke server! Pastikan server Flask berjalan.</div>", unsafe_allow_html=True)
            st.sidebar.code("python Main/alur.py", language="bash")

# Tombol refresh dashboard
if st.sidebar.button("🔄 Refresh Dashboard", type="secondary"):
    st.rerun()

# Tambahkan informasi sumber data di sidebar
if MONGO_ENABLED and (mongo_sensor_collection is not None or mongo_cv_collection is not None):
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Sumber Data")
    st.sidebar.markdown(f"""
    <div style="border-left: 3px solid #4da6ff; padding-left: 10px;">
    <strong>MongoDB:</strong> {MONGO_DB}<br/>
    <small>• Sensor: {MONGO_SENSOR_COLLECTION}</small><br/>
    <small>• Aktivitas: {MONGO_CV_COLLECTION}</small>
    </div>
    """, unsafe_allow_html=True)
else:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Sumber Data")
    st.sidebar.markdown(f"""
    <div style="border-left: 3px solid #ffa64d; padding-left: 10px;">
    <strong>File JSON Lokal</strong><br/>
    <small>• Sensor: {SENSOR_FILE}</small><br/>
    <small>• Aktivitas: {CV_FILE}</small>
    </div>
    """, unsafe_allow_html=True)

# Buat tab untuk memisahkan dashboard dan deteksi
tab1, tab2 = st.tabs(["📊 Dashboard Monitoring", "🔍 Hasil Deteksi"])

with tab1:
    # Tampilkan header dengan styling
    st.markdown(f'<h1 class="main-header">📊 FACTS Monitoring Dashboard</h1>', unsafe_allow_html=True)
    st.markdown(f'<h2 class="sub-header">Monitoring Data untuk {ternak_icons[selected_ternak]} {selected_ternak.capitalize()}</h2>', unsafe_allow_html=True)
    
    # Helper function untuk memformat waktu
    def format_timestamp(timestamp_str):
        try:
            # Coba beberapa format datetime yang umum
            try:
                # Format dengan milidetik
                dt = datetime.fromisoformat(timestamp_str)
            except ValueError:
                # Format tanpa milidetik
                if 'T' in timestamp_str and len(timestamp_str) == 19:
                    dt = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S")
                else:
                    # Format lainnya
                    dt = pd.to_datetime(timestamp_str).to_pydatetime()
            
            return dt.strftime("%d/%m/%Y %H:%M:%S")
        except Exception:
            return timestamp_str
    
    # Fungsi untuk membaca data sensor dari MongoDB
    def load_sensor_data_from_mongo():
        try:
            if not MONGO_ENABLED or mongo_sensor_collection is None:
                return None
            
            # Ambil semua data dari koleksi sensor
            cursor = mongo_sensor_collection.find({})
            data = list(cursor)
            
            if not data:
                return None
            
            # Konversi ObjectId ke string agar bisa diproses oleh pandas
            for item in data:
                if '_id' in item:
                    item['_id'] = str(item['_id'])
                # Konversi datetime ke string ISO format untuk konsistensi dengan JSON
                if 'timestamp' in item and isinstance(item['timestamp'], datetime):
                    item['timestamp'] = item['timestamp'].isoformat()
                
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"Error membaca data sensor dari MongoDB: {e}")
            st.error(traceback.format_exc())
            return None

    # Fungsi untuk membaca data aktivitas dari MongoDB
    def load_cv_data_from_mongo():
        try:
            if not MONGO_ENABLED or mongo_cv_collection is None:
                return None
            
            # Ambil semua data dari koleksi aktivitas
            cursor = mongo_cv_collection.find({})
            data = list(cursor)
            
            if not data:
                return None
            
            # Konversi ObjectId ke string agar bisa diproses oleh pandas
            for item in data:
                if '_id' in item:
                    item['_id'] = str(item['_id'])
                # Konversi datetime ke string ISO format untuk konsistensi dengan JSON
                if 'timestamp' in item and isinstance(item['timestamp'], datetime):
                    item['timestamp'] = item['timestamp'].isoformat()
                
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"Error membaca data aktivitas dari MongoDB: {e}")
            st.error(traceback.format_exc())
            return None

    # Update fungsi load_sensor_data untuk mencoba MongoDB terlebih dahulu dan menyeragamkan format timestamp
    def load_sensor_data():
        # Coba baca dari MongoDB terlebih dahulu jika diaktifkan
        if MONGO_ENABLED and mongo_sensor_collection is not None:
            mongo_data = load_sensor_data_from_mongo()
            if mongo_data is not None and not mongo_data.empty:
                return mongo_data
            
        # Fallback ke file JSON jika MongoDB tidak tersedia atau tidak ada data
        try:
            # Cek apakah file ada
            if not os.path.exists(SENSOR_FILE):
                st.warning(f"File sensor tidak ditemukan di: {SENSOR_FILE}")
                # Buat file kosong
                with open(SENSOR_FILE, "w") as f:
                    json.dump([], f)
                return pd.DataFrame()
                
            # Baca file dengan path absolut
            with open(SENSOR_FILE, "r") as f:
                data = json.load(f)
                
            # Pastikan format timestamp konsisten
            for item in data:
                if 'timestamp' in item and not isinstance(item['timestamp'], str):
                    item['timestamp'] = str(item['timestamp'])
                
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"Error membaca data sensor: {e}")
            return pd.DataFrame()

    # Tampilkan data sensor
    sensor_data_df = load_sensor_data()
    
    if not sensor_data_df.empty:
        # Filter data berdasarkan jenis ternak jika field 'ternak' ada
        if 'ternak' in sensor_data_df.columns:
            filtered_df = sensor_data_df[sensor_data_df['ternak'] == selected_ternak]
            if not filtered_df.empty:
                sensor_data_df = filtered_df
        
        # Format timestamp
        if 'timestamp' in sensor_data_df.columns:
            # Konversi kolom timestamp ke datetime untuk plotting
            try:
                # Coba konversi dengan format ISO fleksibel
                sensor_data_df['timestamp'] = pd.to_datetime(sensor_data_df['timestamp'], format='ISO8601', errors='coerce')
                
                # Jika masih ada NaT (timestamp tidak valid), coba format lain
                if sensor_data_df['timestamp'].isna().any():
                    mask = sensor_data_df['timestamp'].isna()
                    # Coba format tanpa milidetik
                    sensor_data_df.loc[mask, 'timestamp'] = pd.to_datetime(
                        sensor_data_df.loc[mask, 'timestamp'].astype(str), 
                        format='%Y-%m-%dT%H:%M:%S',
                        errors='coerce'
                    )
            except Exception as e:
                st.error(f"Error saat konversi timestamp: {str(e)}")
                # Fallback ke konversi umum
                sensor_data_df['timestamp'] = pd.to_datetime(sensor_data_df['timestamp'], errors='coerce')
            
            # Buat kolom timestamp_formatted untuk tampilan
            sensor_data_df['timestamp_formatted'] = sensor_data_df['timestamp'].apply(lambda x: x.strftime("%d/%m/%Y %H:%M:%S") if pd.notna(x) else "")
            
            # Urutkan data
            sensor_data_df = sensor_data_df.sort_values('timestamp', ascending=False)
        
        # Tampilkan metrik dan visualisasi data
        st.markdown('<h3 class="sub-header">Kondisi Ternak Saat Ini</h3>', unsafe_allow_html=True)
        
        # Ambil data terbaru
        latest_data = sensor_data_df.iloc[0] if not sensor_data_df.empty else None
        
        if latest_data is not None:
            # Tampilkan metrik dalam card bergaya
            cols = st.columns(4)
            with cols[0]:
                # Suhu dengan indikator visual
                suhu = latest_data['suhu']
                suhu_color = success_color if 30 <= suhu <= 35 else error_color  # hijau jika normal, merah jika abnormal
                st.markdown(f"""
                <div class="card" style="border-left: 5px solid {suhu_color};">
                    <h4 style="margin:0; color: {text_color};">Suhu</h4>
                    <div style="font-size: 2rem; font-weight: bold; color: {suhu_color};">{suhu} °C</div>
                    <div style="color: {text_color}; opacity: 0.7; font-size: 0.8rem;">Terakhir diupdate: {latest_data['timestamp_formatted'] if 'timestamp_formatted' in latest_data else '-'}</div>
                </div>
                """, unsafe_allow_html=True)
            
            with cols[1]:
                # Kelembapan dengan indikator visual
                kelembapan = latest_data['kelembapan']
                kelembapan_color = success_color if 50 <= kelembapan <= 70 else error_color
                st.markdown(f"""
                <div class="card" style="border-left: 5px solid {kelembapan_color};">
                    <h4 style="margin:0; color: {text_color};">Kelembapan</h4>
                    <div style="font-size: 2rem; font-weight: bold; color: {kelembapan_color};">{kelembapan} %</div>
                    <div style="color: {text_color}; opacity: 0.7; font-size: 0.8rem;">Terakhir diupdate: {latest_data['timestamp_formatted'] if 'timestamp_formatted' in latest_data else '-'}</div>
                </div>
                """, unsafe_allow_html=True)
                
            with cols[2]:
                # Kualitas Udara dengan indikator visual
                kualitas_udara = latest_data['kualitas_udara']
                udara_color = success_color if kualitas_udara < 200 else error_color
                st.markdown(f"""
                <div class="card" style="border-left: 5px solid {udara_color};">
                    <h4 style="margin:0; color: {text_color};">Kualitas Udara</h4>
                    <div style="font-size: 2rem; font-weight: bold; color: {udara_color};">{kualitas_udara} ppm</div>
                    <div style="color: {text_color}; opacity: 0.7; font-size: 0.8rem;">Terakhir diupdate: {latest_data['timestamp_formatted'] if 'timestamp_formatted' in latest_data else '-'}</div>
                </div>
                """, unsafe_allow_html=True)
                
            with cols[3]:
                # Jarak Pakan jika ada
                if 'jarak_pakan' in latest_data:
                    jarak_pakan = latest_data['jarak_pakan']
                    pakan_color = success_color if jarak_pakan < 10 else error_color
                    st.markdown(f"""
                    <div class="card" style="border-left: 5px solid {pakan_color};">
                        <h4 style="margin:0; color: {text_color};">Jarak Pakan</h4>
                        <div style="font-size: 2rem; font-weight: bold; color: {pakan_color};">{jarak_pakan} cm</div>
                        <div style="color: {text_color}; opacity: 0.7; font-size: 0.8rem;">Terakhir diupdate: {latest_data['timestamp_formatted'] if 'timestamp_formatted' in latest_data else '-'}</div>
                    </div>
                    """, unsafe_allow_html=True)
        
        # Tampilkan data sensor dalam tabel interaktif
        st.markdown('<h3 class="sub-header">Data Sensor Terbaru</h3>', unsafe_allow_html=True)
        
        # Gunakan AgGrid untuk tabel interaktif jika tersedia
        display_cols = [col for col in sensor_data_df.columns if col != 'timestamp_formatted' and col not in ['test']]
        if 'timestamp_formatted' in sensor_data_df.columns:
            display_cols = ['timestamp_formatted'] + [col for col in display_cols if col != 'timestamp']
        
        st.dataframe(
            sensor_data_df[display_cols].head(5),
            use_container_width=True,
            hide_index=True
        )
        
        # Tampilkan grafik untuk data sensor jika ada minimal 2 entri data
        if len(sensor_data_df) >= 2:
            st.markdown('<h3 class="sub-header">Grafik Data Sensor</h3>', unsafe_allow_html=True)
            
            # Konversi kolom timestamp ke datetime untuk plotting
            if 'timestamp' in sensor_data_df.columns:
                # Gunakan format yang lebih fleksibel untuk konversi timestamp
                try:
                    # Coba konversi dengan format ISO fleksibel
                    sensor_data_df['timestamp'] = pd.to_datetime(sensor_data_df['timestamp'], format='ISO8601', errors='coerce')
                    
                    # Jika masih ada NaT (timestamp tidak valid), coba format lain
                    if sensor_data_df['timestamp'].isna().any():
                        mask = sensor_data_df['timestamp'].isna()
                        # Coba format tanpa milidetik
                        sensor_data_df.loc[mask, 'timestamp'] = pd.to_datetime(
                            sensor_data_df.loc[mask, 'timestamp'].astype(str), 
                            format='%Y-%m-%dT%H:%M:%S',
                            errors='coerce'
                        )
                except Exception as e:
                    st.error(f"Error saat konversi timestamp: {str(e)}")
                    # Fallback ke konversi umum
                    sensor_data_df['timestamp'] = pd.to_datetime(sensor_data_df['timestamp'], errors='coerce')
                
                # Tab untuk berbagai jenis grafik
                chart_tabs = st.tabs(["Suhu", "Kelembapan", "Kualitas Udara", "Semua Parameter"])
                
                with chart_tabs[0]:
                    # Plot suhu dengan Plotly
                    fig_suhu = px.line(
                        sensor_data_df.sort_values('timestamp'), 
                        x='timestamp', 
                        y='suhu',
                        title=f'Suhu untuk {selected_ternak.capitalize()} (°C)',
                        labels={'suhu': 'Suhu (°C)', 'timestamp': 'Waktu'},
                        markers=True
                    )
                    fig_suhu.update_layout(
                        xaxis_title="Waktu",
                        yaxis_title="Suhu (°C)",
                        hovermode="x unified",
                        template="plotly_white" if not dark_mode else "plotly_dark"
                    )
                    # Tambahkan garis batas normal
                    fig_suhu.add_shape(type="line", x0=sensor_data_df['timestamp'].min(), x1=sensor_data_df['timestamp'].max(),
                                  y0=30, y1=30, line=dict(color=success_color, width=2, dash="dash"))
                    fig_suhu.add_shape(type="line", x0=sensor_data_df['timestamp'].min(), x1=sensor_data_df['timestamp'].max(),
                                  y0=35, y1=35, line=dict(color=error_color, width=2, dash="dash"))
                    st.plotly_chart(fig_suhu, use_container_width=True)
                
                with chart_tabs[1]:
                    # Plot kelembapan dengan Plotly
                    fig_kelembapan = px.line(
                        sensor_data_df.sort_values('timestamp'), 
                        x='timestamp', 
                        y='kelembapan',
                        title=f'Kelembapan untuk {selected_ternak.capitalize()} (%)',
                        labels={'kelembapan': 'Kelembapan (%)', 'timestamp': 'Waktu'},
                        markers=True
                    )
                    fig_kelembapan.update_layout(
                        xaxis_title="Waktu",
                        yaxis_title="Kelembapan (%)",
                        hovermode="x unified",
                        template="plotly_white" if not dark_mode else "plotly_dark"
                    )
                    # Tambahkan garis batas normal
                    fig_kelembapan.add_shape(type="line", x0=sensor_data_df['timestamp'].min(), x1=sensor_data_df['timestamp'].max(),
                                        y0=50, y1=50, line=dict(color=success_color, width=2, dash="dash"))
                    fig_kelembapan.add_shape(type="line", x0=sensor_data_df['timestamp'].min(), x1=sensor_data_df['timestamp'].max(),
                                        y0=70, y1=70, line=dict(color=error_color, width=2, dash="dash"))
                    st.plotly_chart(fig_kelembapan, use_container_width=True)
                
                with chart_tabs[2]:
                    # Plot kualitas udara jika ada
                    if 'kualitas_udara' in sensor_data_df.columns:
                        fig_udara = px.line(
                            sensor_data_df.sort_values('timestamp'), 
                            x='timestamp', 
                            y='kualitas_udara',
                            title=f'Kualitas Udara untuk {selected_ternak.capitalize()} (ppm)',
                            labels={'kualitas_udara': 'Kualitas Udara (ppm)', 'timestamp': 'Waktu'},
                            markers=True
                        )
                        fig_udara.update_layout(
                            xaxis_title="Waktu",
                            yaxis_title="Kualitas Udara (ppm)",
                            hovermode="x unified",
                            template="plotly_white" if not dark_mode else "plotly_dark"
                        )
                        # Tambahkan garis batas normal
                        fig_udara.add_shape(type="line", x0=sensor_data_df['timestamp'].min(), x1=sensor_data_df['timestamp'].max(),
                                      y0=200, y1=200, line=dict(color=error_color, width=2, dash="dash"))
                        st.plotly_chart(fig_udara, use_container_width=True)
                
                with chart_tabs[3]:
                    # Plot semua parameter dalam satu grafik
                    fig_all = go.Figure()
                    fig_all.add_trace(go.Scatter(x=sensor_data_df['timestamp'], y=sensor_data_df['suhu'],
                                        mode='lines+markers', name='Suhu (°C)'))
                    fig_all.add_trace(go.Scatter(x=sensor_data_df['timestamp'], y=sensor_data_df['kelembapan'],
                                        mode='lines+markers', name='Kelembapan (%)'))
                    if 'kualitas_udara' in sensor_data_df.columns:
                        fig_all.add_trace(go.Scatter(x=sensor_data_df['timestamp'], y=sensor_data_df['kualitas_udara'] / 10,  # Skala untuk memudahkan visualisasi
                                            mode='lines+markers', name='Kualitas Udara (ppm/10)'))
                    
                    fig_all.update_layout(
                        title=f'Semua Parameter untuk {selected_ternak.capitalize()}',
                        xaxis_title="Waktu",
                        yaxis_title="Nilai",
                        hovermode="x unified",
                        template="plotly_white" if not dark_mode else "plotly_dark",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    st.plotly_chart(fig_all, use_container_width=True)
    else:
        st.warning("Belum ada data sensor. Pastikan:")
        st.info("1. Server Flask berjalan: `python Main/alur.py`")
        st.info("2. Sensor mengirim data: `python Main/Sensor.py --ternak " + selected_ternak + "`")
        st.info("3. Atau klik tombol 'Tes Koneksi & Kirim Data' di sidebar")

    # Show activity (CV) data
    # Update fungsi load_cv_data untuk mencoba MongoDB terlebih dahulu dan menyeragamkan format timestamp
    def load_cv_data():
        # Coba baca dari MongoDB terlebih dahulu jika diaktifkan
        if MONGO_ENABLED and mongo_cv_collection is not None:
            mongo_data = load_cv_data_from_mongo()
            if mongo_data is not None and not mongo_data.empty:
                return mongo_data
            
        # Fallback ke file JSON jika MongoDB tidak tersedia atau tidak ada data
        try:
            # Cek apakah file ada
            if not os.path.exists(CV_FILE):
                st.warning(f"File aktivitas tidak ditemukan di: {CV_FILE}")
                # Buat file kosong
                with open(CV_FILE, "w") as f:
                    json.dump([], f)
                return pd.DataFrame()
                
            # Baca file dengan path absolut
            with open(CV_FILE, "r") as f:
                data = json.load(f)
                
            # Pastikan format timestamp konsisten
            for item in data:
                if 'timestamp' in item and not isinstance(item['timestamp'], str):
                    item['timestamp'] = str(item['timestamp'])
                
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"Error membaca data aktivitas: {e}")
            return pd.DataFrame()

    cv_data_df = load_cv_data()
    
    # Filter data aktivitas berdasarkan jenis ternak
    if not cv_data_df.empty and 'ternak' in cv_data_df.columns:
        filtered_cv_df = cv_data_df[cv_data_df['ternak'] == selected_ternak]
        if not filtered_cv_df.empty:
            cv_data_df = filtered_cv_df
    
    # Format timestamp untuk tampilan
    if not cv_data_df.empty and 'timestamp' in cv_data_df.columns:
        # Konversi timestamp ke format datetime
        try:
            # Coba konversi dengan format ISO fleksibel
            cv_data_df['timestamp'] = pd.to_datetime(cv_data_df['timestamp'], format='ISO8601', errors='coerce')
                  
            # Jika masih ada NaT (timestamp tidak valid), coba format lain
            if cv_data_df['timestamp'].isna().any():
                mask = cv_data_df['timestamp'].isna()
                # Coba format tanpa milidetik
                cv_data_df.loc[mask, 'timestamp'] = pd.to_datetime(
                    cv_data_df.loc[mask, 'timestamp'].astype(str), 
                    format='%Y-%m-%dT%H:%M:%S',
                    errors='coerce'
                )
        except Exception as e:
            st.error(f"Error saat konversi timestamp CV: {str(e)}")
            # Fallback ke konversi umum
            cv_data_df['timestamp'] = pd.to_datetime(cv_data_df['timestamp'], errors='coerce')
        
        # Buat kolom timestamp_formatted untuk tampilan
        cv_data_df['timestamp_formatted'] = cv_data_df['timestamp'].apply(lambda x: x.strftime("%d/%m/%Y %H:%M:%S") if pd.notna(x) else "")
        
        # Urutkan data
        cv_data_df = cv_data_df.sort_values('timestamp', ascending=False)
    
    st.markdown(f'<h3 class="sub-header">Aktivitas Ternak Terbaru ({ternak_icons[selected_ternak]} {selected_ternak.capitalize()})</h3>', unsafe_allow_html=True)
    
    if not cv_data_df.empty:
        # Tampilkan data aktivitas dalam tabel interaktif
        display_cols = [col for col in cv_data_df.columns if col != 'timestamp_formatted' and col not in ['test']]
        if 'timestamp_formatted' in cv_data_df.columns:
            display_cols = ['timestamp_formatted'] + [col for col in display_cols if col != 'timestamp']
        
        st.dataframe(
            cv_data_df[display_cols].head(5),
            use_container_width=True,
            hide_index=True
        )
        
        # Jika ada kolom confidence, tampilkan visualisasi
        if 'confidence' in cv_data_df.columns and len(cv_data_df) > 1:
            st.markdown('<h3 class="sub-header">Grafik Deteksi Ternak</h3>', unsafe_allow_html=True)
            
            # Format data untuk visualisasi
            if 'timestamp' in cv_data_df.columns:
                # Konversi timestamp sudah dilakukan sebelumnya, tidak perlu dikonversi lagi
                # Buat grafik confidence dari waktu ke waktu
                fig_conf = px.line(
                    cv_data_df.sort_values('timestamp').tail(20),  # ambil 20 deteksi terakhir saja
                    x='timestamp', 
                    y='confidence',
                    title=f'Tingkat Kepercayaan Deteksi {selected_ternak.capitalize()} (%)',
                    labels={'confidence': 'Confidence (%)', 'timestamp': 'Waktu'},
                    markers=True,
                    color_discrete_sequence=[primary_color]
                )
                fig_conf.update_layout(
                    xaxis_title="Waktu",
                    yaxis_title="Confidence (%)",
                    hovermode="x unified",
                    template="plotly_white" if not dark_mode else "plotly_dark",
                    yaxis=dict(range=[0, 1.1])  # skala 0-1 untuk confidence
                )
                fig_conf.update_traces(marker=dict(size=10))
                st.plotly_chart(fig_conf, use_container_width=True)
                
                # Hitung aktivitas per jam
                if len(cv_data_df) > 5:
                    cv_data_df['hour'] = cv_data_df['timestamp'].dt.hour
                    activity_by_hour = cv_data_df.groupby('hour').size().reset_index(name='count')
                    
                    # Plot histogram aktivitas per jam
                    fig_activity = px.bar(
                        activity_by_hour,
                        x='hour',
                        y='count',
                        title=f'Aktivitas {selected_ternak.capitalize()} per Jam',
                        labels={'count': 'Jumlah Aktivitas', 'hour': 'Jam'},
                        color_discrete_sequence=[secondary_color]
                    )
                    fig_activity.update_layout(
                        xaxis_title="Jam",
                        yaxis_title="Jumlah Aktivitas",
                        hovermode="x unified",
                        template="plotly_white" if not dark_mode else "plotly_dark",
                        xaxis=dict(tickmode='linear', tick0=0, dtick=1)  # tunjukkan semua jam
                    )
                    st.plotly_chart(fig_activity, use_container_width=True)
    else:
        st.info("Belum ada data aktivitas ternak.")
        st.info("Aktifkan deteksi di sidebar atau jalankan: `python Main/Camera.py --ternak " + selected_ternak + "`")

    # Inisialisasi klien Google Gemini dengan API key
    client = genai.Client(api_key=API_GEMINI)

    # Section untuk analisis AI dengan styling yang lebih menarik
    st.markdown('<h3 class="sub-header">🤖 Analisis AI</h3>', unsafe_allow_html=True)
    
    # Button untuk generate AI Resume
    if st.button("Buat Resume AI", type="primary", use_container_width=True):
        if not sensor_data_df.empty and not cv_data_df.empty:
            # Tampilkan spinner saat memuat
            with st.spinner("AI sedang menganalisis data..."):
                # Ambil data terbaru untuk resume
                latest_data = sensor_data_df.iloc[0]
                cv_latest = cv_data_df.iloc[0]

                # Format data untuk Gemini dengan format Markdown
                prompt = f"""
                Analisis kondisi ternak {selected_ternak.capitalize()} berdasarkan data berikut:
                
                **Data Sensor:**
                - Suhu: {latest_data['suhu']}°C
                - Kelembapan: {latest_data['kelembapan']}%
                - Kualitas Udara: {latest_data['kualitas_udara']} ppm
                - {'Jarak Pakan: '+str(latest_data['jarak_pakan'])+' cm' if 'jarak_pakan' in latest_data else ''}
                
                **Aktivitas Terdeteksi:**
                - {cv_latest['aktivitas']}
                
                Berikan analisis dalam format Markdown yang terstruktur dengan bagian:
                
                ## Status Kesehatan
                *[sehat/waspada/kritis]* - Deskripsi singkat status kesehatan ternak.
                
                ## Indikator Utama
                *Jelaskan parameter yang paling perlu diperhatikan dengan format bullet points*
                
                ## Rekomendasi Tindakan
                *Minimal 3 poin tindakan konkret dengan format numbered list*
                1. Tindakan pertama
                2. Tindakan kedua
                3. Tindakan ketiga
                
                ## Antisipasi
                *Langkah-langkah antisipasi dengan format bullet points*
                
                Gunakan format Markdown dengan heading, list, dan emphasis. Pastikan responsmu terstruktur sesuai format di atas.
                """

                # Kirim data ke API Gemini (Google Cloud) menggunakan google-genai
                try:
                    response = client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=prompt,
                    )
                    analysis = response.text
                    
                    # Proses hasil analisis untuk tampilan Markdown
                    # Deteksi status kesehatan untuk warna kartu
                    status_color = success_color
                    if "kritis" in analysis.lower() or "buruk" in analysis.lower() or "bahaya" in analysis.lower():
                        status_color = error_color
                    elif "waspada" in analysis.lower() or "perhatian" in analysis.lower() or "peringatan" in analysis.lower():
                        status_color = warning_color
                    
                except Exception as e:
                    analysis = f"### Error\nGagal menghubungi API Gemini: {e}"
                    status_color = error_color
                
                # Tampilkan hasil analisis dengan st.markdown untuk format Markdown
                st.markdown(f'<div class="card" style="border-left: 5px solid {status_color}; padding: 0;">', unsafe_allow_html=True)
                
                # Header informasi
                st.markdown(f"""
                <div style="padding: 1rem 1.5rem; border-bottom: 1px solid {border_color}; background-color: {card_bg};">
                    <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                        <span style="font-size: 1.5rem; margin-right: 0.5rem;">{ternak_icons[selected_ternak]}</span>
                        <h3 style="margin: 0; color: {text_color};">Analisis Ternak {selected_ternak.capitalize()}</h3>
                    </div>
                    <div style="color: {text_color}; opacity: 0.7; font-size: 0.8rem;">
                        Data terakhir: {latest_data['timestamp_formatted'] if 'timestamp_formatted' in latest_data else '-'}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Konten analisis dalam format Markdown
                with st.container():
                    st.markdown(analysis)
                
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Tambahkan informasi parameter ideal
                st.markdown(f"""
                <div class="card" style="margin-top: 1.5rem;">
                    <h4 style="color: {primary_color}; margin-top: 0;">💡 Parameter Ideal {selected_ternak.capitalize()}</h4>
                    <table style="width: 100%; border-collapse: collapse; margin-top: 0.5rem;">
                        <tr>
                            <th style="padding: 8px; text-align: left; border-bottom: 1px solid {border_color}; color: {text_color};">Parameter</th>
                            <th style="padding: 8px; text-align: left; border-bottom: 1px solid {border_color}; color: {text_color};">Nilai Ideal</th>
                            <th style="padding: 8px; text-align: left; border-bottom: 1px solid {border_color}; color: {text_color};">Status Saat Ini</th>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid {border_color}; color: {text_color};">Suhu</td>
                            <td style="padding: 8px; border-bottom: 1px solid {border_color}; color: {text_color};">{
                            "32°C - 37°C" if selected_ternak == "ayam" else
                            "25°C - 32°C" if selected_ternak == "sapi" else
                            "27°C - 34°C" # kambing
                            }</td>
                            <td style="padding: 8px; border-bottom: 1px solid {border_color}; color: {success_color if (
                                (selected_ternak == 'ayam' and 32 <= latest_data['suhu'] <= 37) or
                                (selected_ternak == 'sapi' and 25 <= latest_data['suhu'] <= 32) or
                                (selected_ternak == 'kambing' and 27 <= latest_data['suhu'] <= 34)
                            ) else error_color};">{latest_data['suhu']}°C {
                            "✓" if (
                                (selected_ternak == 'ayam' and 32 <= latest_data['suhu'] <= 37) or
                                (selected_ternak == 'sapi' and 25 <= latest_data['suhu'] <= 32) or
                                (selected_ternak == 'kambing' and 27 <= latest_data['suhu'] <= 34)
                            ) else "⚠️"
                            }</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid {border_color}; color: {text_color};">Kelembapan</td>
                            <td style="padding: 8px; border-bottom: 1px solid {border_color}; color: {text_color};">{
                            "50% - 70%" if selected_ternak == "ayam" else
                            "60% - 80%" if selected_ternak == "sapi" else
                            "40% - 65%" # kambing
                            }</td>
                            <td style="padding: 8px; border-bottom: 1px solid {border_color}; color: {success_color if (
                                (selected_ternak == 'ayam' and 50 <= latest_data['kelembapan'] <= 70) or
                                (selected_ternak == 'sapi' and 60 <= latest_data['kelembapan'] <= 80) or
                                (selected_ternak == 'kambing' and 40 <= latest_data['kelembapan'] <= 65)
                            ) else error_color};">{latest_data['kelembapan']}% {
                            "✓" if (
                                (selected_ternak == 'ayam' and 50 <= latest_data['kelembapan'] <= 70) or
                                (selected_ternak == 'sapi' and 60 <= latest_data['kelembapan'] <= 80) or
                                (selected_ternak == 'kambing' and 40 <= latest_data['kelembapan'] <= 65)
                            ) else "⚠️"
                            }</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid {border_color}; color: {text_color};">Kualitas Udara</td>
                            <td style="padding: 8px; border-bottom: 1px solid {border_color}; color: {text_color};">< 200 ppm</td>
                            <td style="padding: 8px; border-bottom: 1px solid {border_color}; color: {success_color if latest_data['kualitas_udara'] < 200 else error_color};">{latest_data['kualitas_udara']} ppm {
                            "✓" if latest_data['kualitas_udara'] < 200 else "⚠️"
                            }</td>
                        </tr>
                        {f'''
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid {border_color}; color: {text_color};">Jarak Pakan</td>
                            <td style="padding: 8px; border-bottom: 1px solid {border_color}; color: {text_color};">< 10 cm</td>
                            <td style="padding: 8px; border-bottom: 1px solid {border_color}; color: {success_color if latest_data['jarak_pakan'] < 10 else error_color};">{latest_data['jarak_pakan']} cm {
                            "✓" if latest_data['jarak_pakan'] < 10 else "⚠️"
                            }</td>
                        </tr>
                        ''' if 'jarak_pakan' in latest_data else ''}
                    </table>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.warning("Tidak ada data sensor atau aktivitas untuk dianalisis. Pastikan data telah terkirim.")
            st.info("Kirim data terlebih dahulu dengan mengklik tombol 'Tes Koneksi & Kirim Data' di sidebar")

    # Tampilkan grafik confidence jika ada data deteksi
    if len(st.session_state.detection_confidence) > 0 and len(st.session_state.detection_times) > 0:
        # Buat data frame dari data deteksi
        detection_df = pd.DataFrame({
            'timestamp': st.session_state.detection_times,
            'confidence': st.session_state.detection_confidence
        })
        
        # Buat grafik confidence menggunakan Plotly
        st.markdown("<h4 style='margin-top: 20px;'>Grafik Confidence Deteksi</h4>", unsafe_allow_html=True)
        fig = px.line(
            detection_df.tail(10),  # Tampilkan 10 deteksi terakhir saja
            x='timestamp',
            y='confidence',
            labels={'confidence': 'Confidence', 'timestamp': 'Waktu'},
            markers=True,
            color_discrete_sequence=[primary_color]
        )
        fig.update_layout(
            xaxis_title="Waktu",
            yaxis_title="Confidence",
            hovermode="x unified",
            template="plotly_white" if not dark_mode else "plotly_dark",
            yaxis=dict(range=[0, 1.1])  # skala 0-1 untuk confidence
        )
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    # Tampilkan header dengan styling untuk hasil deteksi
    st.markdown(f'<h1 class="main-header">🔍 Hasil Deteksi {ternak_icons[selected_ternak]} {selected_ternak.capitalize()}</h1>', unsafe_allow_html=True)
    
    # Mengaktifkan kamera jika tombol start ditekan
    if start_detection and camera_active and not st.session_state.detection_running:
        st.session_state.detection_running = True
        if camera_type == "Webcam":
            try:
                # Buat session state untuk menyimpan informasi kamera
                st.session_state.camera_stream = cv2.VideoCapture(0)
                # st.session_state.camera_stream = cv2.VideoCapture(IP ESP32CAM)
                if not st.session_state.camera_stream.isOpened():
                    st.error("Tidak dapat mengakses kamera. Pastikan kamera terhubung dan tidak digunakan aplikasi lain.")
                    st.session_state.detection_running = False
            except Exception as e:
                st.error(f"Error membuka kamera: {e}")
                st.session_state.detection_running = False
    
    # Menonaktifkan kamera jika tombol stop ditekan
    if stop_detection and st.session_state.detection_running:
        if st.session_state.camera_stream is not None:
            st.session_state.camera_stream.release()
        st.session_state.detection_running = False
        st.success("Deteksi dihentikan")
    
    # Buat layout 2 kolom untuk hasil deteksi
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Placeholder untuk video results
        st.markdown(f'<div class="card"><h3 style="text-align: center; color: {text_color};">Hasil Kamera</h3></div>', unsafe_allow_html=True)
        camera_placeholder = st.empty()
        
        # Jika deteksi sedang berjalan, tampilkan stream
        if st.session_state.detection_running and camera_active:
            # Load model deteksi
            try:
                model_paths = MODEL_PATHS
                
                # Periksa apakah model ada
                model_path = model_paths[selected_ternak]
                if not os.path.exists(model_path):
                    st.error(f"Model untuk {selected_ternak} tidak ditemukan di {model_path}. Silakan pastikan file model tersedia.")
                    st.session_state.detection_running = False
                else:
                    # Tampilkan status loading
                    with st.status(f"Memuat model {selected_ternak}...") as status:
                        model = YOLO(model_path)
                        status.update(label=f"Model {selected_ternak} berhasil dimuat!", state="complete", expanded=False)
                
                # Deteksi menggunakan Webcam
                if camera_type == "Webcam" and st.session_state.camera_stream is not None:
                    # Baca frame dari kamera
                    ret, frame = st.session_state.camera_stream.read()
                    if ret:
                        # Run deteksi
                        results = model(frame)
                        annotated_frame = results[0].plot()
                        
                        # Tambahkan timestamp
                        current_time = datetime.now()
                        cv2.putText(
                            annotated_frame, 
                            current_time.strftime("%Y-%m-%d %H:%M:%S"), 
                            (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 
                            1, 
                            (255, 255, 255), 
                            2
                        )
                        
                        # Tampilkan frame dalam placeholder
                        camera_placeholder.image(annotated_frame, channels="BGR", caption=f"Deteksi {selected_ternak.capitalize()}", use_container_width=True)
                        
                        # Update counter deteksi
                        if len(results[0].boxes) > 0:
                            st.session_state.detection_counter += 1
                            confidence = float(results[0].boxes[0].conf[0]) if len(results[0].boxes) > 0 else 0.0
                            st.session_state.detection_confidence.append(confidence)
                            st.session_state.detection_times.append(current_time)
                            
                            # Kirim data ke server
                            aktivitas_data = {
                                "ternak": selected_ternak,
                                "aktivitas": f"Terdeteksi {len(results[0].boxes)} {selected_ternak}",
                                "confidence": confidence,
                                "timestamp": current_time.isoformat()
                            }
                            try:
                                requests.post(API_URL_CV, json=aktivitas_data)
                            except Exception as e:
                                st.warning(f"Gagal mengirim data ke server: {e}")
                    else:
                        camera_placeholder.error("Tidak dapat membaca frame dari kamera")
                        st.session_state.detection_running = False
            except Exception as e:
                st.error(f"Error saat deteksi: {e}")
                st.session_state.detection_running = False
        else:
            # Tampilkan placeholder gambar/video
            camera_placeholder.markdown(f"""
            <div style="height: 400px; display: flex; align-items: center; justify-content: center; 
                        border: 2px dashed {border_color}; border-radius: 10px; background-color: {card_bg};">
                <div style="text-align: center; padding: 20px; color: {text_color};">
                    <div style="font-size: 48px;">📷</div>
                    <div style="font-size: 18px; margin-top: 15px;">
                        {f'Aktifkan kamera di sidebar dan klik "▶️ Mulai Deteksi"' if not st.session_state.detection_running else 'Memuat stream kamera...'}
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        # Status card untuk deteksi
        status_text = "AKTIF" if st.session_state.detection_running else "TIDAK AKTIF"
        status_icon = "✅" if st.session_state.detection_running else "❌"
        status_desc = f"Mendeteksi {selected_ternak}" if st.session_state.detection_running else "Tekan tombol Mulai Deteksi"
        
        st.markdown(f"""
        <div class="card" style="margin-bottom: 20px; border-left: 5px solid {primary_color if st.session_state.detection_running else error_color};">
            <h4 style="margin:0; color: {text_color};">Status Deteksi {status_icon}</h4>
            <div style="font-size: 1.2rem; font-weight: bold; color: {primary_color if st.session_state.detection_running else error_color};">
                {status_text}
            </div>
            <div style="color: {text_color}; opacity: 0.7; font-size: 0.8rem;">
                {status_desc}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Metrik untuk jumlah deteksi
        st.markdown(f"""
        <div class="card" style="border-left: 5px solid {secondary_color};">
            <h4 style="margin:0; color: {text_color};">Jumlah Deteksi</h4>
            <div style="font-size: 2rem; font-weight: bold; color: {secondary_color};">
                {st.session_state.detection_counter}
            </div>
            <div style="color: {text_color}; opacity: 0.7; font-size: 0.8rem;">
                Total deteksi yang berhasil dilakukan
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Petunjuk penggunaan
        st.markdown(f"""
        <div class="card" style="margin-top: 20px; border-left: 5px solid {primary_color};">
            <h4 style="margin:0; color: {text_color};">Petunjuk Penggunaan</h4>
            <ul style="color: {text_color}; margin-top: 10px; padding-left: 20px;">
                <li>1. Aktifkan kamera di sidebar</li>
                <li>2. Pilih sumber: webcam atau video</li>
                <li>3. Klik tombol "▶️ Mulai Deteksi"</li>
                <li>4. Klik "⏹️ Hentikan" untuk berhenti</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        # Tombol refresh kamera secara manual
        if st.button("🔄 Refresh Kamera", disabled=not camera_active):
            if st.session_state.camera_stream is not None:
                st.session_state.camera_stream.release()
            
            try:
                st.session_state.camera_stream = cv2.VideoCapture(0)
                if st.session_state.camera_stream.isOpened():
                    st.success("Kamera berhasil di-refresh!")
                else:
                    st.error("Tidak dapat mengakses kamera setelah refresh.")
            except Exception as e:
                st.error(f"Error saat refresh kamera: {e}")
        
        # Status kamera
        if camera_active:
            webcam_status = "Terhubung" if (st.session_state.camera_stream is not None and 
                                         st.session_state.camera_stream.isOpened()) else "Tidak terhubung"
            webcam_icon = "✅" if (st.session_state.camera_stream is not None and 
                               st.session_state.camera_stream.isOpened()) else "❌"
            
            st.markdown(f"""
            <div style="margin-top: 20px; padding: 10px; border-radius: 5px; background-color: {card_bg}; 
                        border-left: 3px solid {success_color if webcam_status == 'Terhubung' else error_color};">
                <div style="font-weight: bold; color: {text_color};">Status Webcam: {webcam_icon} {webcam_status}</div>
                <div style="color: {text_color}; opacity: 0.7; font-size: 0.8rem;">
                    {f"Kamera aktif dan siap digunakan" if webcam_status == 'Terhubung' else "Coba refresh kamera atau restart aplikasi"}
                </div>
            </div>
            """, unsafe_allow_html=True)

# Tutup kamera saat aplikasi ditutup
def on_shutdown():
    if "camera_stream" in st.session_state and st.session_state.camera_stream is not None:
        st.session_state.camera_stream.release()
    
    # Tutup koneksi MongoDB jika ada
    if mongo_client is not None:
        mongo_client.close()

# Schedule shutdown hook
import atexit
atexit.register(on_shutdown)

# Footer untuk menampilkan info tentang tema
st.markdown("---")
st.markdown(f"""
<div style="display: flex; justify-content: space-between; padding: 10px 0;">
    <span style="color: {text_color}; opacity: 0.7;">Mode Tampilan: {'Gelap' if dark_mode else 'Terang'}</span>
    <span style="color: {text_color}; opacity: 0.7;">Ubah tema di ⚙️ Settings > Theme</span>
</div>
""", unsafe_allow_html=True)

# Run Streamlit
if __name__ == "__main__":
    st.write("FACTS Dashboard is running...")
