import requests
from bs4 import BeautifulSoup
import re
import time
import urllib3
from database import *
import mysql.connector
from datetime import datetime

# Nonaktifkan peringatan keamanan untuk koneksi HTTPS lokal
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
MYSQL_CONFIG = {
    'host': '192.168.1.12',      
    'user': 'akane',           
    'password': 'akaneyama123',           
    'database': 'jaringanftth' 
}
def kirimdatakedb(alamat_ip, pon, online, offline,statuspon):
    """
    Fungsi untuk MEMPERBARUI (UPDATE) data ONU di database MySQL menggunakan WHERE.
    """
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()
        timestamp = datetime.now()

        # Perintah SQL untuk UPDATE dengan klausa WHERE
        sql_query = '''
            UPDATE olt 
            SET 
                status_pon = %s,
                online = %s, 
                offline = %s,
                terakhir_update = %s
            WHERE 
                ip_olt = %s AND pon_scraping = %s
        '''
        
        # Urutan data harus sesuai dengan urutan %s di query
        # Nilai untuk SET di depan, nilai untuk WHERE di belakang
        data_to_update = (statuspon,online, offline, timestamp, alamat_ip, pon)
        
        cursor.execute(sql_query, data_to_update)
        conn.commit()
        
        # Pengecekan apakah ada baris yang di-update
        if cursor.rowcount == 0:
            print(f"-> DB WARNING: Tidak ada data yang diupdate untuk {pon} di {alamat_ip}. "
                  f"Pastikan baris datanya sudah ada di database.")
        else:
            print(f"-> DB: Data untuk {pon} di {alamat_ip} berhasil di-update.")
            
    except mysql.connector.Error as e:
        print(f"❌ DB Error: Gagal mengupdate data untuk {pon}. Error: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

def cekdanupdatestatusgpon(alamat_ip):
    BASE_URL = f"https://{alamat_ip}" 
    USERNAME = "akane"
    PASSWORD = "akaneyama123" # <-- Ganti dengan password Anda
    LOGIN_URL = f"{BASE_URL}/action/main.html"

    # --- Fungsi Bantuan untuk Scraping ---

    def scrape_olt_info(html_content):
        """Fungsi untuk mengambil info umum dari OLT (Device Model, Hostname, dll)."""
        # ... (tidak ada perubahan di sini)
        info = {}
        soup = BeautifulSoup(html_content, 'lxml')
        model_label = soup.find('font', attrs={'data-i18n-text': 'deviceModel'})
        if model_label:
            model_value_td = model_label.find_parent('td').find_next_sibling('td')
            if model_value_td:
                info['Device Model'] = model_value_td.text.strip()
        hostname_input = soup.find('input', attrs={'name': 'hostname'})
        if hostname_input:
            info['Hostname'] = hostname_input['value']
        return info

    def scrape_gpon_onu_data(html_content):
        """
        Fungsi untuk MENGHITUNG jumlah ONU berdasarkan WARNA status (Online/Offline).
        Ini adalah metode yang paling akurat.
        """
        # --- KONFIGURASI WARNA ---
        ONLINE_COLOR = "#008040"
        OFFLINE_COLOR = "#ff0000" # <-- GANTI INI dengan warna untuk status offline hasil inspect element!
        # -------------------------

        soup = BeautifulSoup(html_content, 'lxml')
        
        # 1. Hitung semua ONU yang berstatus "Online" berdasarkan warnanya
        online_tags = soup.find_all('font', attrs={'color': ONLINE_COLOR})
        online_count = len(online_tags)
        
        # 2. Hitung semua ONU yang berstatus "Offline" berdasarkan warnanya
        offline_tags = soup.find_all('font', attrs={'color': OFFLINE_COLOR})
        offline_count = len(offline_tags)
        
        # 3. Hitung total dengan menjumlahkan keduanya
        total_count = online_count + offline_count
        
        # 4. Buat teks status untuk ditampilkan
        status_text = f"Dihitung via warna: {online_count} Online, {offline_count} Offline"
        
        return {
            "online": online_count,
            "offline": offline_count,
            "total": total_count,
            "status_text": status_text
        }

    # --- Alur Script Utama ---
    # (Tidak ada perubahan di sini)
    print(f"Mencoba login ke {LOGIN_URL}...")
    try:
        with requests.Session() as session:
            # ... (Kode Login tidak berubah) ...
            login_data = {"user": USERNAME, "pass": PASSWORD, "button": "Login", "who": "100"}
            headers = {'Referer': f"{BASE_URL}/action/login.html"}
            response = session.post(LOGIN_URL, data=login_data, headers=headers, verify=False)

            if not (response.status_code == 200 and 'loginout.html' in response.text):
                print("\n❌ Login Gagal.")
                exit()
            print("✅ Login Berhasil!")
            
            # ... (Kode ambil info OLT tidak berubah) ...
            info_url = f"{BASE_URL}/action/systeminfo.html"
            info_response = session.get(info_url, verify=False)
            if info_response.status_code == 200:
                olt_info = scrape_olt_info(info_response.text)
                print("\n--- Informasi OLT ---")
                for key, value in olt_info.items():
                    print(f"{key}: {value}")
                print("---------------------\n")
            
            # 3. PROSES SETIAP PON PORT
            gpon_list_url = f"{BASE_URL}/action/onuauthinfo.html"
            initial_gpon_page = session.get(gpon_list_url, verify=False)
            soup_initial = BeautifulSoup(initial_gpon_page.text, 'lxml')
            
            select_tag = soup_initial.find('select', {'name': 'select'})
            if not select_tag:
                print(f"❌ Tidak dapat menemukan dropdown PON di halaman {gpon_list_url}.")
                exit()
                
            pon_list = [{'value': opt['value'], 'text': opt.text.strip()} 
                        for opt in select_tag.find_all('option')]
            
            if not pon_list:
                print("❌ Tidak dapat menemukan pilihan PON di dalam dropdown.")
                exit()
                
            print(f"✅ Menemukan {len(pon_list)} PON port. Memulai proses scraping ONU...\n")

            for pon in pon_list:
                pon_value = pon['value']
                pon_text = pon['text']
                
                print(f"--- Mengecek {pon_text} (value={pon_value}) ---")
                
                params = {'select': pon_value}
                pon_page_response = session.get(gpon_list_url, params=params, verify=False)
                
                onu_data = scrape_gpon_onu_data(pon_page_response.text)
                
                if onu_data:
                    print(f"Status: {onu_data['status_text']}")
                    print(f"Hasil: Online={onu_data['online']}, Offline={onu_data['offline']}, Total={onu_data['total']}\n")
                    statuspon1 = 'tersedia';
                    if onu_data['online'] >= 122:
                        statuspon1 = 'habis';
                    kirimdatakedb(alamat_ip,pon['text'],onu_data['online'],onu_data['offline'],statuspon1);
                else:
                
                    print("Gagal menghitung data ONU dari tabel untuk PON ini.\n")
                
                time.sleep(1)

    except requests.exceptions.ConnectionError:
        print(f"\n❌ Gagal terhubung ke {BASE_URL}. Periksa alamat IP dan koneksi jaringan.")
    except Exception as e:
        print(f"\nTerjadi error yang tidak terduga: {e}")