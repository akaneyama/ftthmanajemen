

import mysql.connector
from pysnmp.hlapi import *
import pandas as pd
import re

DB_CONFIG = {
    'host': '192.168.1.12',
    'user': 'akane',      
    'password': 'akaneyama123', 
    'database': 'jaringanftth'
}


COMMUNITY = "public"      
PORT = 161

# --- OID (Object Identifiers) ---
OID_IFDESCR = "1.3.6.1.2.1.2.2.1.2"
OID_IFOPERSTATUS = "1.3.6.1.2.1.2.2.1.8"

def get_olts_from_db():
    """
    Menghubungi database untuk mendapatkan daftar OLT yang unik.
    """
    olts = []
    try:
        print("Menghubungi database...")
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT nama_olt, ip_olt FROM olt ORDER BY nama_olt")
        olts = cursor.fetchall()
        cursor.close()
        conn.close()
        print(f"Berhasil mendapatkan {len(olts)} OLT unik dari database.")
    except mysql.connector.Error as err:
        print(f"Error Database: {err}")
    return olts

def snmp_walk(olt_ip, oid):
    """
    Fungsi untuk melakukan SNMP walk ke OLT tertentu.
    """
    for (errorIndication,
         errorStatus,
         errorIndex,
         varBinds) in nextCmd(SnmpEngine(),
                             CommunityData(COMMUNITY, mpModel=0),
                             UdpTransportTarget((olt_ip, PORT), timeout=2, retries=1),
                             ContextData(),
                             ObjectType(ObjectIdentity(oid)),
                             lexicographicMode=False):
        if errorIndication: return
        elif errorStatus: return
        else:
            for varBind in varBinds:
                yield varBind

# def update_pon_stats_in_db(db_conn, olt_name, pon_port, online_count, offline_count):
#     """
#     Memperbarui kolom online, offline, dan status_pon di database.
#     """
#     try:
#         new_status = 'tersedia' if online_count < 61 else 'habis'
#         cursor = db_conn.cursor()
#         sql = """
#             UPDATE olt 
#             SET online = %s, offline = %s, status_pon = %s 
#             WHERE nama_olt = %s AND pon_olt = %s
#         """
#         val = (online_count, offline_count, new_status, olt_name, pon_port)
#         cursor.execute(sql, val)
        
#         if cursor.rowcount > 0:
#             print(f"  -> DB Update: {pon_port} di {olt_name} -> Online: {online_count}, Offline: {offline_count}, Status: '{new_status}'")
#         else:
#             print(f"  -> DB Warning: Tidak ada baris yang cocok untuk {pon_port} di {olt_name} untuk diupdate.")
#         cursor.close()
#     except mysql.connector.Error as err:
#         print(f"  -> GAGAL DB Update untuk {pon_port}: {err}")


def update_pon_stats_in_db(db_conn, olt_name, pon_port, online_count, offline_count):
    """
    Memperbarui kolom online, offline, dan status_pon di database
    dengan logika kapasitas yang berbeda untuk GPON dan EPON.
    """
    try:
        # --- PERUBAHAN LOGIKA DI SINI ---
        # Tentukan batas kapasitas berdasarkan tipe PON
        kapasitas_maksimal = 125 if 'GPON' in olt_name.upper() else 61
        
        # Tentukan status baru berdasarkan perbandingan dengan kapasitas maksimal
        new_status = 'tersedia' if online_count < kapasitas_maksimal else 'habis'
        
        cursor = db_conn.cursor()
        sql = """
            UPDATE olt 
            SET 
                online = %s, 
                offline = %s, 
                status_pon = %s 
            WHERE 
                nama_olt = %s AND pon_olt = %s
        """
        val = (online_count, offline_count, new_status, olt_name, pon_port)
        cursor.execute(sql, val)
        
        if cursor.rowcount > 0:
            print(f"  -> DB Update: {pon_port} di {olt_name} -> Online: {online_count}, Offline: {offline_count}, Status: '{new_status}' (Kapasitas: {kapasitas_maksimal})")
        else:
            print(f"  -> DB Warning: Tidak ada baris yang cocok untuk {pon_port} di {olt_name} untuk diupdate.")
        cursor.close()

    except mysql.connector.Error as err:
        print(f"  -> GAGAL DB Update untuk {pon_port}: {err}")

def process_olt(olt_name, olt_ip):
    """
    Fungsi utama untuk memproses satu OLT.
    """
    print(f"\n{'='*20} Memproses OLT: {olt_name} ({olt_ip}) {'='*20}")

    # ... (bagian ambil data SNMP tetap sama) ...
    interface_names_gen = snmp_walk(olt_ip, OID_IFDESCR)
    if not interface_names_gen:
        print(f"Gagal terhubung atau tidak ada respon SNMP dari {olt_name}.")
        return
    interface_names = {str(oid).split('.')[-1]: str(val) for oid, val in interface_names_gen}
    interface_statuses = {str(oid).split('.')[-1]: ("Online" if str(val) == '1' else "Offline") for oid, val in snmp_walk(olt_ip, OID_IFOPERSTATUS)}
    if not interface_names or not interface_statuses:
        print(f"Tidak mendapatkan data lengkap dari {olt_name}.")
        return

    df = pd.DataFrame(list(interface_names.items()), columns=['Index', 'Nama Interface'])
    df_status = pd.DataFrame(list(interface_statuses.items()), columns=['Index', 'Status'])
    df_final = pd.merge(df, df_status, on='Index', how='left')

    df_onu = df_final[df_final['Nama Interface'].str.contains("EPON|GPON|ONU", case=False, na=False)].copy()

    if df_onu.empty:
        print(f"Tidak ada interface ONU ditemukan di {olt_name}.")
        return

    # --- FUNGSI DIPERBAIKI DI SINI ---
    def get_pon_port(interface_name):
        """
        Mengekstrak nama PON utama dari nama interface ONU.
        Contoh: 'EPON0/1:12' -> 'EPON0/1'
                 'gpon-onu_1/1/1.10' -> 'gpon-onu_1/1/1'
                 'EPON01ONU20' -> 'EPON01'
        """
        # Cari pemisah seperti ':' atau '.'
        match = re.match(r'(.+?)[.:]', interface_name)
        if match:
            return match.group(1)
        
        # Jika tidak ada pemisah, cari pola '...ONU...'
        if "ONU" in interface_name.upper():
            # Ambil bagian sebelum kata "ONU"
            return interface_name.upper().split("ONU")[0]
            
        # Jika tidak ada pola yang cocok, kembalikan nama aslinya
        return interface_name

    df_onu['PON Port'] = df_onu['Nama Interface'].apply(get_pon_port)
    
    # (Opsional) Tambahkan baris ini jika Anda ingin melihat hasil pengelompokan sebelum diupdate ke DB
    # print("\n--- Hasil Pengelompokan Port PON ---")
    # print(df_onu[['Nama Interface', 'PON Port']])
    
    # --- Proses Agregasi (Sama seperti sebelumnya, tapi sekarang seharusnya benar) ---
    summary = df_onu.groupby('PON Port')['Status'].value_counts().unstack(fill_value=0)
    if 'Online' not in summary.columns: summary['Online'] = 0
    if 'Offline' not in summary.columns: summary['Offline'] = 0
    
    print(f"\n--- Ringkasan Data Agregat dari {olt_name} ---")
    print(summary)
    
    print("\n--- Memulai Proses Update Database ---")
    try:
        db_conn = mysql.connector.connect(**DB_CONFIG)
        for pon_port, row in summary.iterrows():
            online_count = int(row['Online'])
            offline_count = int(row['Offline'])
            
            # Memastikan nama pon_port cocok dengan yang ada di DB (misal: EPON01 bukan EPON0/1)
            # Anda bisa menyesuaikan ini jika perlu
            formatted_pon_port = pon_port.replace('/', '') 
            
            update_pon_stats_in_db(db_conn, olt_name, formatted_pon_port, online_count, offline_count)
        
        db_conn.commit()
        db_conn.close()
    except mysql.connector.Error as err:
        print(f"Gagal membuka koneksi DB untuk melakukan update: {err}")

def reloadsemuadataolt():
    list_olt = get_olts_from_db()
    if not list_olt:
        print("Tidak ada OLT untuk diproses. Program berhenti.")
        return
        
    for nama_olt, ip_olt in list_olt:
        process_olt(nama_olt, ip_olt)

    print(f"\n{'='*25} SEMUA PROSES SELESAI {'='*25}")

if __name__ == "__main__":
    reloadsemuadataolt()