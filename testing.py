import mysql.connector
from mysql.connector import Error

# Salin konfigurasi database Anda dari file database.py
DB_CONFIG = {
    'host': '192.168.1.12',
    'user': 'akane',         
    'password': 'akaneyama123',     
    'database': 'jaringanftth'
}

def seed_odc_data():
    """
    Fungsi untuk menambahkan data ODC sesuai format yang diinginkan.
    """
    print("Mencoba terhubung ke database...")
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        if conn.is_connected():
            print("Koneksi database berhasil.")
            cursor = conn.cursor()

            # Variabel sesuai keinginan Anda
            nama_prefix = "OLT_"
            port_prefix = "PON_"
            
            total_added = 0
            
            # Loop untuk 4 ODC group
            for i in range(1, 5):
                # Loop untuk 24 core per group
                for j in range(1, 5):
                    # Buat nama dan port sesuai format
                    nama_odc = f"{nama_prefix}{i}"
                    port_odc = f"{port_prefix}{j}"

                    # Gunakan INSERT IGNORE agar script tidak berhenti jika data duplikat
                    # (misalnya jika Anda menjalankan script ini dua kali)
                    sql = "INSERT IGNORE INTO olt (nama_olt, pon_olt) VALUES (%s, %s)"
                    
                    cursor.execute(sql, (nama_odc, port_odc))
                    
                    # Cek apakah baris baru benar-benar ditambahkan
                    if cursor.rowcount > 0:
                        total_added += 1
                        print(f"Menambahkan: nama_odc='{nama_odc}', port_odc='{port_odc}'")

            # Simpan semua perubahan ke database
            conn.commit()
            print(f"\nSelesai! {total_added} data ODC baru berhasil ditambahkan.")

    except Error as e:
        print(f"Error saat menjalankan script: {e}")
    
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
            print("Koneksi database ditutup.")

# Jalankan fungsi utama saat script dieksekusi
if __name__ == '__main__':
    seed_odc_data()