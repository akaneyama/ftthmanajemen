from werkzeug.security import generate_password_hash
import mysql.connector
from mysql.connector import Error
import getpass # Untuk menyembunyikan input password

# Konfigurasi database Anda
DB_CONFIG = {
    'host': '192.168.1.12',
    'user': 'akane',         
    'password': 'akaneyama123',     
    'database': 'jaringanftth'
}

def add_user():
    try:
        username = input("Masukkan username baru: ").strip()
        
        # Pilihan Role
        while True:
            role = input("Masukkan role (admin / superadmin): ").strip().lower()
            if role in ['admin', 'superadmin']:
                break
            print("Role tidak valid. Harap masukkan 'admin' atau 'superadmin'.")

        password = getpass.getpass("Masukkan password baru: ")
        password_confirm = getpass.getpass("Konfirmasi password baru: ")

        if not username or not password:
            print("Username dan password tidak boleh kosong.")
            return
        if password != password_confirm:
            print("Password tidak cocok. Silakan coba lagi.")
            return

        hashed_password = generate_password_hash(password)

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Masukkan user baru dengan rolenya
        sql = "INSERT INTO users (username, role, password_hash) VALUES (%s, %s, %s)"
        cursor.execute(sql, (username, role, hashed_password))
        conn.commit()

        print(f"\nSukses! Pengguna '{username}' dengan role '{role}' berhasil dibuat.")

    except Error as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
if __name__ == '__main__':
    add_user()