import mysql.connector
from mysql.connector import Error
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth
import urllib3
import time

# Menonaktifkan peringatan untuk koneksi tanpa verifikasi SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =================================================================
# === KONFIGURASI (PASTIKAN SESUAI DENGAN SETUP ANDA) ============
# =================================================================
DB_CONFIG = {
    'host': '192.168.1.12',
    'user': 'akane',         
    'password': 'akaneyama123',     
    'database': 'jaringanftth'
}

ROUTER_KIT = "lbkampoengit.daffaaditya.my.id:43987"
ROUTER_KPUTIH = "lbkampoengit.daffaaditya.my.id:43989"
USERNAME_MIKROTIK = "akane"
PASSWORD_MIKROTIK = "akaneyama123"

# Daftar interface spesifik yang ingin direkam historinya
ISP_INTERFACES_TO_MONITOR = [
    {'router_alias': 'ROUTER KIT', 'interface_name': '1-ISP'},
    {'router_alias': 'ROUTER KIT', 'interface_name': '1-ISP-SFP2-MARS DATA'}
]
# =================================================================

def get_mikrotik_api_data(base_url):
    """Mengambil data dari endpoint API MikroTik tertentu."""
    try:
        response = requests.get(base_url, auth=HTTPBasicAuth(USERNAME_MIKROTIK, PASSWORD_MIKROTIK), verify=False, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] Gagal menghubungi {base_url}: {e}")
        return None

def get_current_traffic(interface_name):
    """Mengambil total byte RX/TX saat ini untuk satu interface."""
    router_endpoints = [
        f"https://{ROUTER_KPUTIH}/rest/interface",
        f"https://{ROUTER_KIT}/rest/interface"
    ]
    for endpoint in router_endpoints:
        interfaces = get_mikrotik_api_data(endpoint)
        if interfaces:
            for iface in interfaces:
                if iface.get('name') == interface_name:
                    rx = int(iface.get('rx-byte', 0))
                    tx = int(iface.get('tx-byte', 0))
                    return rx, tx
    # Jika interface tidak ditemukan di semua router
    return None, None

def record_hourly_traffic_summary():
    """
    Fungsi utama yang mengambil sampel traffic, menghitung statistik,
    dan menyimpannya ke database.
    """
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Memulai script perekaman ringkasan traffic...")
    
    for interface_info in ISP_INTERFACES_TO_MONITOR:
        interface_name = interface_info['interface_name']
        print(f"\nMemproses interface: {interface_name}...")
        
        traffic_samples = {'download': [], 'upload': []}
        
        # Ambil sampel traffic selama 60 detik (12 kali polling setiap 5 detik)
        print("--> Mengambil sampel traffic selama 60 detik...")
        
        last_rx, last_tx = get_current_traffic(interface_name)
        if last_rx is None:
            print(f"  [GAGAL] Tidak bisa mendapatkan data awal untuk {interface_name}. Dilewati.")
            continue
            
        # Proses sampling
        sampling_duration = 60 # detik
        sampling_interval = 5 # detik
        num_samples = int(sampling_duration / sampling_interval)

        for i in range(num_samples):
            time.sleep(sampling_interval)
            current_rx, current_tx = get_current_traffic(interface_name)

            if current_rx is not None and current_rx >= last_rx:
                # Hitung perbedaan byte dalam interval, lalu ubah ke Mbps
                rx_delta_bytes = current_rx - last_rx
                tx_delta_bytes = current_tx - last_tx
                
                rx_rate_mbps = (rx_delta_bytes * 8 / sampling_interval) / 1000000
                tx_rate_mbps = (tx_delta_bytes * 8 / sampling_interval) / 1000000
                
                traffic_samples['download'].append(rx_rate_mbps)
                traffic_samples['upload'].append(tx_rate_mbps)
                print(f"    Sampel {i+1}/{num_samples}: DL={rx_rate_mbps:.2f} Mbps, UL={tx_rate_mbps:.2f} Mbps")

            # Update nilai terakhir untuk perhitungan selanjutnya
            last_rx, last_tx = current_rx, current_tx
        
        if not traffic_samples['download']:
            print(f"  [PERINGATAN] Tidak ada data traffic yang valid terkumpul untuk {interface_name}. Dilewati.")
            continue

        # Hitung statistik dari semua sampel yang terkumpul
        avg_download = sum(traffic_samples['download']) / len(traffic_samples['download'])
        avg_upload = sum(traffic_samples['upload']) / len(traffic_samples['upload'])
        peak_download = max(traffic_samples['download'])
        peak_upload = max(traffic_samples['upload'])

        print(f"--> Statistik untuk {interface_name}: Rata-rata D/U: {avg_download:.2f}/{avg_upload:.2f} Mbps | Puncak D/U: {peak_download:.2f}/{peak_upload:.2f} Mbps")

        # Simpan ringkasan ke database
        conn = None
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor()
            
            # Waktu log dibulatkan ke jam saat ini
            log_time = datetime.now().replace(minute=0, second=0, microsecond=0)
            
            sql = """
                INSERT INTO hourly_traffic_logs 
                (log_timestamp, interface_name, avg_download_mbps, avg_upload_mbps, peak_download_mbps, peak_upload_mbps)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            params = (log_time, interface_name, avg_download, avg_upload, peak_download, peak_upload)
            cursor.execute(sql, params)
            conn.commit()
            print(f"  [OK] Ringkasan traffic untuk {interface_name} berhasil disimpan ke database.")
        except Error as e:
            print(f"  [ERROR] Gagal menyimpan ke DB: {e}")
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()

# Jalankan fungsi utama saat script dieksekusi dari command line
if __name__ == '__main__':
    record_hourly_traffic_summary()