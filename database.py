import mysql.connector
from mysql.connector import Error


DB_CONFIG = {
    'host': '192.168.1.12',
    'user': 'akane',         
    'password': 'akaneyama123',     
    'database': 'jaringanftth'
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        if conn.is_connected():
            return conn
    except Error as e:
        print(f"Error saat menghubungkan ke MySQL: {e}")
        return None