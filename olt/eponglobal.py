import requests
from bs4 import BeautifulSoup
import re
import time
import urllib3
import mysql.connector
from datetime import datetime

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


# alamat_ip = "192.168.65.100"
def cekdanupdatestatusepon(alamat_ip,nomor):
    BASE_URL = f"http://{alamat_ip}" 
    USERNAME = "akane"
    PASSWORD = "akaneyama123" 
    LOGIN_URL = f"{BASE_URL}/action/main.html"



    login_data = {
        "user": USERNAME,
        "pass": PASSWORD,
        "button": "Login",
        "who": "100"
    }

    def get_onu_count(html_content):
        soup = BeautifulSoup(html_content, 'lxml')
        font_tag = soup.find('font', attrs={'color': '#ff0000'})
        if font_tag:
            text = font_tag.text.strip()
            numbers = re.findall(r'\d+', text)
            if len(numbers) >= 2:
                return int(numbers[0]), int(numbers[1]), text
        return None, None, "Teks status tidak ditemukan."

    with requests.Session() as session:
        try:
            headers = {'Referer': f"{BASE_URL}/action/login.html"}
            response = session.post(LOGIN_URL, data=login_data, headers=headers )

            if response.status_code == 200 and 'loginout.html' in response.text:
                print("✅ Login Berhasil!")
                
                info_url = f"{BASE_URL}/action/systeminfo.html"
                print(f"Mengambil data dari halaman: {info_url}...")
                info_response = session.get(info_url)

                if info_response.status_code == 200:

                    soup = BeautifulSoup(info_response.text, 'lxml')
                    print("\n----------------------------------")
                    print(f"Data OLT {BASE_URL}")

                    font_tag = soup.find('font', attrs={'data-i18n-text': 'deviceModel'})

                    if font_tag:

                        value_td = font_tag.find_parent('td').find_next_sibling('td')
                        
                        if value_td:
                            device_model = value_td.text.strip()
                            print("----------------------------------")
                            print(f"Device Model: {device_model}")
                    
                        else:
                            print("❌ Gagal: Sel nilai untuk Device Model tidak ditemukan.")

                        input_tag = soup.find('input', attrs={'name': 'hostname'})

                        if input_tag:
                            hostname = input_tag['value']
                            print(f"Hostname: {hostname}")
                        else:
                            print("❌ Gagal: Input field 'hostname' tidak ditemukan.")

                        mac_tag = soup.find('font', attrs={'data-i18n-text': 'macAddress'})
                        if mac_tag:
                            value_td = mac_tag.find_parent('td').find_next_sibling('td')
                            if value_td:
                                device_mac = value_td.text.strip()

                                print(f"Mac Address: {device_mac}")
                                
                            else:
                                print("❌ Gagal: Sel nilai untuk Device Model tidak ditemukan.")

                        cpu_tag = soup.find('font', attrs={'data-i18n-text': 'cpuUsage'})
                        if mac_tag:
                            value_td = cpu_tag.find_parent('td').find_next_sibling('td')
                            if value_td:
                                device_cpu = value_td.text.strip()

                                print(f"Cpu Usage: {device_cpu}")
                            
                            else:
                                print("❌ Gagal: Sel nilai untuk Device Model tidak ditemukan.")

                        memory_tag = soup.find('font', attrs={'data-i18n-text': 'memoryUsage'})
                        if mac_tag:
                            value_td = memory_tag.find_parent('td').find_next_sibling('td')
                            if value_td:
                                device_memory = value_td.text.strip()

                                print(f"Memory Usage: {device_memory}")
                                print("----------------------------------")
                            else:
                                print("❌ Gagal: Sel nilai untuk Device Model tidak ditemukan.")

                    else:
                        print("❌ Gagal: Label 'Device Model' tidak ditemukan di halaman.")

                    
                else:
                    print(f"Gagal mengakses halaman info, status code: {info_response.status_code}")

            

            else:
                print("\n❌ Login Gagal. Username atau password mungkin salah.")

        except requests.exceptions.ConnectionError as e:
            print(f"\n❌ Gagal terhubung ke {BASE_URL}.")
        except Exception as e:
            print(f"\nTerjadi error yang tidak terduga: {e}")

    with requests.Session() as session:
        try:
            login_data = {"user": USERNAME, "pass": PASSWORD, "button": "Login", "who": "100"}
            headers = {'Referer': f"{BASE_URL}/action/login.html"}
            response = session.post(LOGIN_URL, data=login_data, headers=headers)

            if not (response.status_code == 200 and 'loginout.html' in response.text):
                print("\n❌ Login Gagal.")
                exit()
            #print("✅ Login Berhasil!")
            
            onu_list_url = f"{BASE_URL}/action/onuauthinfo.html"
            initial_onu_page = session.get(onu_list_url)
            soup_initial = BeautifulSoup(initial_onu_page.text, 'lxml')
            pon_list = [{'value': opt['value'], 'text': opt.text.strip()} for opt in soup_initial.find_all('option')]
            
            if not pon_list:
                print("❌ Tidak dapat menemukan pilihan PON.")
                exit()
            #print(f"✅ Menemukan {len(pon_list)} pilihan PON. Memulai proses...\n")

        
            for pon in pon_list:
                pon_value = pon['value']
                pon_text = pon['text']
                
                print(f"--- Mengecek PON: {pon_text} (value={pon_value}) ---")
                
                params = {'select': pon_value}
                pon_page_response = session.get(onu_list_url, params=params)
                
                online_onu, total_onu, status_text = get_onu_count(pon_page_response.text)
                
                if online_onu is not None:
                    print(f"Status Awal: {status_text}")
                    if nomor = 1: 
                    if total_onu > online_onu:
                        print(f"⚠️ Ditemukan {total_onu - online_onu} ONU offline. Mencoba menghapus...")
                        

                        session_key = None
            
                        match = re.search(r"SessionKey\.value = '([^']+)';", pon_page_response.text)
                        if match:
                            session_key = match.group(1)
                            print(f"Ditemukan SessionKey: {session_key}")
                        else:
                            print("❌ Gagal menemukan SessionKey di halaman. Membatalkan aksi hapus.")
                            continue 

                        delete_url = f"{BASE_URL}/action/onuauthinfo.html"
                        delete_payload = {
                            'select': pon_value,
                            'onutype': '0',
                            'searchMac': '',
                            'searchDescription': '',
                            'onuid': '0/',
                            'select2': '1/',
                            'who': '9', 
                            'SessionKey': session_key 
                        }
                        
                        print(f"Mengirim permintaan POST untuk menghapus...")
                        
                        delete_response = session.post(delete_url, data=delete_payload, headers=headers)
                        
                        if delete_response.status_code == 200:
                            print("✅ Permintaan hapus berhasil dikirim. Verifikasi hasil...")
                            time.sleep(3)
                            
                            pon_page_after_delete = session.get(onu_list_url, params=params)
                            new_online, new_total, new_status = get_onu_count(pon_page_after_delete.text)
                            
                            print(f"Status Baru: {new_status}")
                            if new_total == online_onu:
                                statuspon = 'tersedia';
                                if new_online >= 61:
                                    statuspon = 'habis';
                                print("🎉 SUKSES! Jumlah ONU total sekarang sama dengan jumlah online sebelumnya.")
                                kirimdatakedb(alamat_ip,pon_text,new_online,new_total-new_online,statuspon)
                            else:
                                print("🤔 PERHATIAN: Jumlah ONU total berubah, tapi tidak sesuai harapan.")
                        else:
                            print(f"❌ Gagal mengirim permintaan hapus. Status Code: {delete_response.status_code}")
                        
                    else:
                        statuspon1 = 'tersedia';
                        if online_onu >= 61:
                            statuspon1 = 'habis';
                        print("✅ Tidak ada ONU offline di PON ini.")
                        kirimdatakedb(alamat_ip,pon_text,online_onu,total_onu - online_onu,statuspon1)
                else:
                    print(f"Tidak dapat membaca status ONU untuk PON ini.")
                
                print("-" * (len(pon_text) + 26) + "\n")
                time.sleep(1)

        except Exception as e:
            print(f"\nTerjadi error yang tidak terduga: {e}")