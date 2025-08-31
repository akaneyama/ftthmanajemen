from flask import Flask, render_template, request, redirect, url_for, flash, session
from database import get_db_connection
import math
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename 
from functools import wraps
import pandas as pd
import io
from flask import Response, jsonify
import requests
from requests.auth import HTTPBasicAuth
import urllib3
import os
import threading
import uuid
import copy
from datetime import datetime
import time
from collections import defaultdict
from olt.eponglobal import cekdanupdatestatusepon
from olt.gponglobal import cekdanupdatestatusgpon

app = Flask(__name__)
app.secret_key = 'kunci_rahasia_untuk_flash_messages' # Diperlukan untuk flash message
tasks = {}
MAINTENANCE_MODE_ACTIVE = False

@app.before_request
def check_for_maintenance():
    """
    Fungsi ini berjalan SEBELUM SETIAP REQUEST ke aplikasi.
    Tugasnya adalah mencegat semua pengunjung jika mode maintenance aktif.
    """
    # 1. Jika maintenance mode TIDAK aktif, hentikan fungsi dan lanjutkan seperti biasa.
    if not MAINTENANCE_MODE_ACTIVE:
        return

    # 2. Izinkan superadmin untuk tetap mengakses situs.
    if session.get('role') == 'superadmin':
        return

    # 3. Izinkan akses ke halaman-halaman penting yang harus tetap berjalan
    #    (login, logout, dan file statis seperti CSS/gambar untuk halaman maintenance).
    if request.endpoint in ['login', 'logout', 'static']:
        return
        
    # 4. Jika semua kondisi di atas tidak terpenuhi, tampilkan halaman maintenance.
    return render_template('error.html'), 503

def run_isolir_task(task_id, ip_list):
    """Fungsi ini berjalan di background, tidak mengganggu aplikasi utama."""
    total_ips = len(ip_list)
    
    # Update status awal
    tasks[task_id]['status'] = 'processing'
    
    for i, ip in enumerate(ip_list):
        ip = ip.strip()
        # Panggil fungsi isolir Anda
        result_text = proses_isolir_per_ip(ip)
        
        # Update progress di dictionary tasks
        # Kita gunakan copy agar aman dari race condition sederhana
        with threading.Lock():
            task_data = copy.deepcopy(tasks[task_id])
            task_data['progress'] = i + 1
            task_data['results'].append(result_text)
            tasks[task_id] = task_data
    
    # Tandai tugas selesai
    tasks[task_id]['status'] = 'completed'
# Menonaktifkan peringatan untuk koneksi tanpa verifikasi SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- KONFIGURASI MIKROTIK ---
ROUTER_KIT = "lbkampoengit.daffaaditya.my.id:43987"
ROUTER_KPUTIH = "lbkampoengit.daffaaditya.my.id:43989"
USERNAME_MIKROTIK = "akane"
PASSWORD_MIKROTIK = "akaneyama123"
BASE_KIT = f"https://{ROUTER_KIT}/rest/ip/hotspot/ip-binding"
BASE_KPUTIH = f"https://{ROUTER_KPUTIH}/rest/ip/hotspot/ip-binding"

# -----------------------------

# --- KONFIGURASI UPLOAD ---
# Buat folder bernama 'uploads' di dalam folder proyek Anda
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER # app adalah instance Flask Anda
# --------------------------
# --- FUNGSI HELPER UNTUK PROSES ISOLIR ---

def get_hotspot_ip_binding(base_url):
    try:
        response = requests.get(base_url, auth=HTTPBasicAuth(USERNAME_MIKROTIK, PASSWORD_MIKROTIK), verify=False, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error API get_hotspot_ip_binding: {e}")
        return None

def set_binding_status(base_url, binding_id, disable=True):
    url = f"{base_url}/{binding_id}"
    payload = {"disabled": "true" if disable else "false"}
    try:
        response = requests.patch(url, json=payload, auth=HTTPBasicAuth(USERNAME_MIKROTIK, PASSWORD_MIKROTIK), verify=False, timeout=10)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error API set_binding_status: {e}")
        return False

def get_router_info_by_ip(ip_address):
    """Menentukan base_url dan lokasi router berdasarkan IP."""
    if ip_address.startswith("192.") or ip_address.startswith("123.") or ip_address.startswith("172.16."):
        return BASE_KIT, "KIT"
    elif ip_address.startswith("193."):
        return BASE_KPUTIH, "KPUTIH"
    else:
        return None, None

def proses_isolir_per_ip(ip_address):
    """Memproses satu IP untuk diisolir, mengembalikan string hasil."""
    ip_address = ip_address.replace("static@", "")
    base_url, lokasi = get_router_info_by_ip(ip_address)
    
    if not base_url:
        return f"[SKIP] IP {ip_address} tidak termasuk dalam jaringan yang dikenali."

    all_bindings = get_hotspot_ip_binding(base_url)
    if all_bindings is None:
        return f"[GAGAL] Tidak dapat menghubungi router {lokasi}."

    binding_id = None
    comment = ""
    is_disabled = False
    for binding in all_bindings:
        if binding.get('address') == ip_address:
            binding_id = binding.get('.id')
            comment = binding.get('comment', '')
            is_disabled = binding.get('disabled') == 'true'
            break
    
    if not binding_id:
        return f"[SKIP] IP {ip_address} tidak ditemukan di router {lokasi}."

    if is_disabled:
        return f"[INFO] Sudah diisolir sebelumnya: {comment} ({ip_address})"

    if set_binding_status(base_url, binding_id, disable=True):
        return f"[OK] Berhasil isolir: {comment} ({ip_address})"
    else:
        return f"[GAGAL] Gagal mengirim permintaan isolir untuk: {comment} ({ip_address})"

# Fungsi get_router_info_by_ip bisa Anda salin langsung dari jawaban sebelumnya
# karena tidak ada perubahan.
def get_router_url_by_ip(ipfix):
    if ipfix.startswith("192.") or ipfix.startswith("123.") or ipfix.startswith("172.16."):
        return BASE_KIT, "KIT"
    elif ipfix.startswith("193."):
        return BASE_KPUTIH, "KPUTIH"
    else:
        return None, None
    
# --- HALAMAN UTAMA ---
# Fungsi untuk Halaman Utama/Dashboard
@app.route('/maintenance')
def maintenance():
    return render_template('error.html')






@app.route('/monitoringsimple')
def monitoringsimple():
    """
    Menampilkan halaman monitoring OLT dengan data dari database
    yang disajikan dalam bentuk kartu.
    """
    conn = get_db_connection()
    if not conn:
        # Jika koneksi gagal, tampilkan halaman error atau pesan
        return "Gagal terhubung ke database.", 500
        
    cursor = conn.cursor(dictionary=True)
    
    # Query untuk mengambil semua data OLT yang relevan
    sql = """
        SELECT 
            nama_olt, 
            pon_olt, 
            status_pon, 
            online, 
            offline 
        FROM olt 
        ORDER BY nama_olt, pon_olt;
    """
    cursor.execute(sql)
    all_olt_data = cursor.fetchall()
    
    cursor.close()
    conn.close()
    

    olts_data = defaultdict(list)
    for row in all_olt_data:
        olts_data[row['nama_olt']].append({
            'pon_olt': row['pon_olt'],
            'status_pon': row['status_pon'],
            'online': row['online'],
            'offline': row['offline']
        })
        
    # Kirim data yang sudah terstruktur ke template
    return render_template('monitoringsimple.html', olts_data=olts_data)

@app.route('/')
def index():
    """Menampilkan halaman utama/dashboard dengan grafik histori yang bisa difilter."""
    
    # ==========================================================
    # ==> BAGIAN YANG HILANG SEBELUMNYA, DITAMBAHKAN KEMBALI <==
    # ==========================================================
    # Definisikan daftar interface yang ingin Anda monitor di kartu traffic
    isp_interfaces_to_monitor = [
        {'router_alias': 'ROUTERKIT', 'interface_name': '1-ISP'},
        {'router_alias': 'ROUTERKIT', 'interface_name': '1-ISP-SFP2-MARS DATA'}
    ]
    # ==========================================================
    # Ambil tanggal dari URL. Jika tidak ada, gunakan tanggal hari ini sebagai default.
    selected_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Query untuk Kartu Statistik
    cursor.execute("SELECT COUNT(*) as total FROM client")
    total_clients = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(DISTINCT nama_olt) AS total FROM olt")
    total_olts = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(DISTINCT nama_odc) AS total FROM odc")
    total_odcs = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as total FROM odp")
    total_odps = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as total FROM fat")
    total_fats = cursor.fetchone()['total']
    stats = {
        'total_clients': total_clients, 
        'total_olts': total_olts, 
        'total_odcs': total_odcs, 
        'total_odps': total_odps, 
        'total_fats': total_fats
    }

    # Query untuk Aktivitas Terbaru
    cursor.execute("SELECT nama_client, alamat_client FROM client ORDER BY id_client DESC LIMIT 5")
    recent_clients = cursor.fetchall()
    
    # Query untuk ODP Terpadat (tanpa kapasitas)
    odp_utilitas = []
    try:
        utilitas_sql = """
            SELECT 
                p.nama_odp,
                (SELECT COUNT(*) FROM rincian_client rc JOIN rincian_odp ro ON rc.id_rodp = ro.id_rodp WHERE ro.id_odp = p.id_odp) as client_count
            FROM odp p
            ORDER BY client_count DESC
            LIMIT 5;
        """
        cursor.execute(utilitas_sql)
        odp_utilitas = cursor.fetchall()
    except Exception as e:
        print(f"Error saat query utilitas ODP: {e}")

    # Query untuk mengambil data grafik histori berdasarkan filter tanggal
    interfaces_to_show = ['1-ISP', '1-ISP-SFP2-MARS DATA']
    placeholders = ','.join(['%s'] * len(interfaces_to_show))
    
    history_sql = f"""
        SELECT 
            DATE_FORMAT(log_timestamp, '%H:00') as hour_label,
            interface_name,
            avg_download_mbps,
            avg_upload_mbps
        FROM hourly_traffic_logs
        WHERE 
            interface_name IN ({placeholders}) AND
            DATE(log_timestamp) = %s
        ORDER BY interface_name, log_timestamp ASC;
    """
    query_params = tuple(interfaces_to_show) + (selected_date,)
    cursor.execute(history_sql, query_params)
    history_logs = cursor.fetchall()

    # Proses data agar siap digunakan oleh Chart.js
    chart_data = {}
    for log in history_logs:
        iface = log['interface_name']
        if iface not in chart_data:
            chart_data[iface] = {'labels': [], 'downloads': [], 'uploads': []}
        
        chart_data[iface]['labels'].append(log['hour_label'])
        chart_data[iface]['downloads'].append(log['avg_download_mbps'])
        chart_data[iface]['uploads'].append(log['avg_upload_mbps'])

    cursor.close()
    conn.close()

    return render_template(
        'index.html', 
        stats=stats, 
        recent_clients=recent_clients,
        odp_utilitas=odp_utilitas,
        chart_data=chart_data,
        selected_date=selected_date,
        isp_interfaces=isp_interfaces_to_monitor # Kirim tanggal yang dipilih ke template
    )


def special_access_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Ambil role dari session
        user_role = session.get('role')
        # Cek apakah rolenya ada di dalam daftar yang diizinkan
        if user_role not in ['superadmin', 'maintenance']:
            flash('Anda tidak memiliki hak akses khusus untuk membuka halaman ini.', 'danger')
            return redirect(url_for('index')) # Arahkan ke halaman utama
        # Jika diizinkan, lanjutkan ke halaman
        return f(*args, **kwargs)
    return decorated_function

def superadmin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'superadmin':
            flash('Anda tidak memiliki hak akses untuk membuka halaman ini.', 'danger')
            return redirect(url_for('index')) # Arahkan ke halaman utama
        return f(*args, **kwargs)
    return decorated_function

def maintenance_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'maintenance':
            flash('Anda tidak memiliki hak akses untuk membuka halaman ini.', 'danger')
            return redirect(url_for('index')) # Arahkan ke halaman utama
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Anda harus login untuk mengakses halaman ini.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            # Jika user ada dan password cocok, buat session
             # <--- TAMBAHKAN INI
            session['logged_in'] = True
            session['username'] = user['username']
            session['user_id'] = user['id'] # <-- TAMBAHKAN BARIS INI
            session['role'] = user['role'] # <-- TAMBAHKAN BARIS INI
            add_log("Login Berhasil")
            flash('Anda berhasil login!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Username atau password salah.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    # Hapus session
    add_log("Logout") # <--- TAMBAHKAN INI
    session.clear()
    flash('Anda berhasil logout.', 'info')
    return redirect(url_for('login'))

# =================================================================
# === CRUD UNTUK MANAJEMEN PENGGUNA ===============================
# =================================================================

@app.route('/users')
@login_required
@superadmin_required # Hanya superadmin yang bisa akses
def user_list():
    """Menampilkan halaman daftar pengguna dengan paginasi dan pencarian."""
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()
    ITEMS_PER_PAGE = 10
    offset = (page - 1) * ITEMS_PER_PAGE

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    params = []
    where_sql = ""
    if search_query:
        where_sql = " WHERE username LIKE %s OR role LIKE %s"
        params.append(f"%{search_query}%")
        params.append(f"%{search_query}%")

    cursor.execute(f"SELECT COUNT(*) as total FROM users{where_sql}", params)
    total_items = cursor.fetchone()['total']
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE) if total_items > 0 else 1

    final_params = params + [ITEMS_PER_PAGE, offset]
    cursor.execute(f"SELECT id, username, role FROM users{where_sql} ORDER BY id DESC LIMIT %s OFFSET %s", final_params)
    users = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    pagination_data = {
        'current_page': page, 'total_pages': total_pages, 'total_items': total_items,
        'start_item': offset + 1 if total_items > 0 else 0, 'end_item': offset + len(users),
        'iter_pages': [p for p in range(max(1, page - 2), min(total_pages, page + 2) + 1)]
    }
    
    return render_template('user_list.html', users=users, pagination=pagination_data, search=search_query)


@app.route('/users/add', methods=['GET', 'POST'])
@login_required
@superadmin_required
def user_add():
    if request.method == 'POST':
        username = request.form['username']
        role = request.form['role']
        password = request.form['password']
        password_confirm = request.form['password_confirm']

        if password != password_confirm:
            flash('Password dan konfirmasi password tidak cocok.', 'danger')
            return redirect(url_for('user_add'))
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            flash(f"Error: Username '{username}' sudah digunakan.", 'danger')
            return redirect(url_for('user_add'))

        hashed_password = generate_password_hash(password)
        
        sql = "INSERT INTO users (username, role, password_hash) VALUES (%s, %s, %s)"
        cursor.execute(sql, (username, role, hashed_password))
        conn.commit()
        
        add_log("Tambah Pengguna", f"Pengguna '{username}' dengan role '{role}' telah dibuat.")
        flash('Pengguna baru berhasil ditambahkan!', 'success')
        
        cursor.close()
        conn.close()
        return redirect(url_for('user_list'))

    return render_template('user_form.html', action='add', user=None)


@app.route('/users/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@superadmin_required
def user_edit(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        username = request.form['username']
        role = request.form['role']
        password = request.form['password']
        password_confirm = request.form['password_confirm']

        cursor.execute("SELECT id FROM users WHERE username = %s AND id != %s", (username, id))
        if cursor.fetchone():
            flash(f"Error: Username '{username}' sudah digunakan oleh pengguna lain.", 'danger')
            return redirect(url_for('user_edit', id=id))

        if password: # Hanya update password jika field diisi
            if password != password_confirm:
                flash('Password dan konfirmasi password tidak cocok.', 'danger')
                return redirect(url_for('user_edit', id=id))
            
            hashed_password = generate_password_hash(password)
            update_sql = "UPDATE users SET username=%s, role=%s, password_hash=%s WHERE id=%s"
            params = (username, role, hashed_password, id)
        else: # Jika password kosong, jangan update password
            update_sql = "UPDATE users SET username=%s, role=%s WHERE id=%s"
            params = (username, role, id)
        
        update_cursor = conn.cursor()
        update_cursor.execute(update_sql, params)
        conn.commit()
        update_cursor.close()

        add_log("Edit Pengguna", f"Data pengguna '{username}' (ID: {id}) telah diperbarui.")
        flash('Data pengguna berhasil diperbarui!', 'success')
        return redirect(url_for('user_list'))

    cursor.execute("SELECT id, username, role FROM users WHERE id=%s", (id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('user_form.html', action='edit', user=user)


@app.route('/users/delete/<int:id>', methods=['POST'])
@login_required
@superadmin_required
def user_delete(id):
    # Mencegah superadmin menghapus dirinya sendiri
    if id == session.get('user_id'):
        flash('Anda tidak dapat menghapus akun Anda sendiri.', 'danger')
        return redirect(url_for('user_list'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Ambil info untuk log sebelum dihapus
    cursor.execute("SELECT username FROM users WHERE id = %s", (id,))
    user = cursor.fetchone()
    
    delete_cursor = conn.cursor()
    delete_cursor.execute("DELETE FROM users WHERE id = %s", (id,))
    conn.commit()
    
    add_log("Hapus Pengguna", f"Pengguna '{user['username'] if user else f'ID {id}'}' telah dihapus.")
    flash('Pengguna berhasil dihapus!', 'danger')
    
    delete_cursor.close()
    cursor.close()
    conn.close()
    return redirect(url_for('user_list'))



@app.route('/api/reload_olt', methods=['POST'])
@login_required
@special_access_required
def api_reload_olt():
    try:
        oltepon = ['192.168.50.100', '192.168.55.100', '192.168.60.100', '192.168.65.100']
        oltgpon = ['192.168.70.100']
        for olts in oltepon:
            cekdanupdatestatusepon(olts,0)

        for oltsgpon in oltgpon:
            cekdanupdatestatusgpon(oltsgpon,0)
        return jsonify({'status': 'success', 'message': 'Data OLT berhasil disinkronkan.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Terjadi kesalahan: {e}'}), 500


@app.route('/api/reload_olt', methods=['POST'])
@login_required
@special_access_required
def api_reload_olt_offline():
    try:
        oltepon = ['192.168.50.100', '192.168.55.100', '192.168.60.100', '192.168.65.100']
        oltgpon = ['192.168.70.100']
        for olts in oltepon:
            cekdanupdatestatusepon(olts,1)

        for oltsgpon in oltgpon:
            cekdanupdatestatusgpon(oltsgpon,1)
        return jsonify({'status': 'success', 'message': 'Data OLT berhasil disinkronkan.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Terjadi kesalahan: {e}'}), 500

# =================================================================
# === CRUD UNTUK CLIENT ===========================================
# =================================================================

@app.route('/clients')
def client_list():
    """Menampilkan data client dengan paginasi dan pencarian."""
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()
    ITEMS_PER_PAGE = 10
    offset = (page - 1) * ITEMS_PER_PAGE

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # --- PENCARIAN DINAMIS ---
    params = []
    where_clauses = []
    if search_query:
        where_clauses.append("(nama_client LIKE %s OR alamat_client LIKE %s OR nomor_telp LIKE %s OR ip_address LIKE %s)")
        search_term = f"%{search_query}%"
        params.extend([search_term, search_term, search_term, search_term])
    
    where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    # Query Hitung Total dengan filter pencarian
    cursor.execute(f"SELECT COUNT(*) as total FROM client{where_sql}", params)
    total_items = cursor.fetchone()['total']
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE) if total_items > 0 else 1

    # Query Ambil Data per Halaman dengan filter pencarian
    final_params = params + [ITEMS_PER_PAGE, offset]
    cursor.execute(f"SELECT * FROM client{where_sql} ORDER BY id_client DESC LIMIT %s OFFSET %s", final_params)
    clients = cursor.fetchall()
    cursor.close()
    conn.close()

    start_item = offset + 1 if total_items > 0 else 0
    end_item = offset + len(clients)
    
    pagination_data = {
        'current_page': page, 'total_pages': total_pages, 'total_items': total_items,
        'start_item': start_item, 'end_item': end_item,
        'iter_pages': [p for p in range(max(1, page - 2), min(total_pages, page + 2) + 1)]
    }

    return render_template('client_list.html', clients=clients, pagination=pagination_data, search=search_query)

@app.route('/clients/add', methods=['GET', 'POST'])
@login_required 
def client_add():
    if request.method == 'POST':
        # Ambil data sebagai list dari form
        list_nama = request.form.getlist('nama_client[]')
        list_alamat = request.form.getlist('alamat_client[]')
        list_telp = request.form.getlist('nomor_telp[]')
        list_ip = request.form.getlist('ip_address[]')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        successful_inserts = 0
        failed_entries = []

        # Loop melalui setiap baris data yang disubmit
        for i in range(len(list_nama)):
            nama = list_nama[i].strip()
            alamat = list_alamat[i].strip()
            telp = list_telp[i].strip()
            ip = list_ip[i].strip()

            # Lewati baris jika data inti (nama dan IP) kosong
            if not nama:
                continue

            # Validasi duplikat untuk setiap baris
            # error_found = False
            # cursor.execute("SELECT id_client FROM client WHERE ip_address = %s", (ip,))
            # if cursor.fetchone():
            #     failed_entries.append(f"'{nama}': IP '{ip}' sudah ada.")
            #     error_found = True
            
            # cursor.execute("SELECT id_client FROM client WHERE nomor_telp = %s", (telp,))
            # if telp and cursor.fetchone():
            #     failed_entries.append(f"'{nama}': No. Telp '{telp}' sudah ada.")
            #     error_found = True
            
            # if error_found:
            #     continue

            # Jika semua validasi lolos, masukkan ke database
            try:
                sql = "INSERT INTO client (nama_client, alamat_client, nomor_telp, ip_address) VALUES (%s, %s, %s, %s)"
                cursor.execute(sql, (nama, alamat, telp, ip))
                successful_inserts += 1
            except Exception as e:
                failed_entries.append(f"'{nama}': Gagal disimpan ({e})")

        # Simpan semua perubahan dan tutup koneksi
        conn.commit()
        cursor.close()
        conn.close()

        # Berikan feedback ke pengguna
        if successful_inserts > 0:
            flash(f'{successful_inserts} client baru berhasil ditambahkan!', 'success')
            add_log("Tambah Client (Batch)", f"{successful_inserts} client baru ditambahkan.") # <--- TAMBAHKAN INI

        if failed_entries:
            flash(f'Beberapa data gagal ditambahkan karena duplikat atau error lain: {"; ".join(failed_entries)}', 'danger')

        return redirect(url_for('client_list'))

    # Untuk method GET, cukup tampilkan halaman form
    return render_template('client_form.html', action='add')

@app.route('/clients/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def client_edit(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        nama = request.form['nama_client']
        alamat = request.form['alamat_client']
        telp = request.form['nomor_telp'].strip()
        ip = request.form['ip_address'].strip()
        
        # Validasi duplikat IP
        cursor.execute("SELECT id_client FROM client WHERE ip_address = %s AND id_client != %s", (ip, id))
        # PENTING: Ambil hasilnya dengan fetchone() untuk membersihkan cursor
        if cursor.fetchone():
            flash(f"Error: IP Address '{ip}' sudah digunakan oleh client lain.", 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('client_edit', id=id))

        # Validasi duplikat Nomor Telepon (hanya jika diisi)
        if telp:
            cursor.execute("SELECT id_client FROM client WHERE nomor_telp = %s AND id_client != %s", (telp, id))
            # PENTING: Ambil hasilnya lagi di sini, meskipun untuk pengecekan
            if cursor.fetchone():
                flash(f"Error: Nomor Telepon '{telp}' sudah digunakan oleh client lain.", 'danger')
                cursor.close()
                conn.close()
                return redirect(url_for('client_edit', id=id))

        # Jika semua validasi lolos, baru lakukan UPDATE
        update_sql = "UPDATE client SET nama_client=%s, alamat_client=%s, nomor_telp=%s, ip_address=%s WHERE id_client=%s"
        # Karena cursor sebelumnya sudah bersih, kita bisa memakainya lagi
        cursor.execute(update_sql, (nama, alamat, telp, ip, id))
        conn.commit()
        
        add_log("Edit Client", f"Data client '{nama}' (ID: {id}) telah diperbarui.")
        flash('Data client berhasil diperbarui!', 'success')
        
        cursor.close()
        conn.close()
        return redirect(url_for('client_list'))

    # Bagian GET request tidak berubah
    cursor.execute("SELECT * FROM client WHERE id_client = %s", (id,))
    client = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not client:
        flash("Client tidak ditemukan.", "danger")
        return redirect(url_for('client_list'))
        
    return render_template('client_form_edit.html', action='edit', client=client)


@app.route('/clients/delete/<int:id>', methods=['POST'])
@login_required 
def client_delete(id):
    """Menghapus data client."""

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT nama_client FROM client WHERE id_client = %s", (id,))
    client = cursor.fetchone()
    client_name = client['nama_client'] if client else f"ID {id}"

    # Proses hapus
    delete_cursor = conn.cursor()
    delete_cursor.execute("DELETE FROM client WHERE id_client = %s", (id,))
    conn.commit()
    delete_cursor.close()
    cursor.close()
    conn.close()
    flash('Client berhasil dihapus!', 'danger')
    add_log("Hapus Client", f"Client '{client_name}' telah dihapus.")
    return redirect(url_for('client_list'))

# =================================================================
# === CRUD UNTUK OLT (Optical Line Terminal) ======================
# =================================================================
@app.route('/olts')
def olt_list():
    """Menampilkan data OLT dengan paginasi dan pencarian."""
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()
    ITEMS_PER_PAGE = 10
    offset = (page - 1) * ITEMS_PER_PAGE

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    params = []
    where_clauses = []
    if search_query:
        where_clauses.append("(nama_olt LIKE %s OR pon_olt LIKE %s)")
        search_term = f"%{search_query}%"
        params.extend([search_term, search_term])

    where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    cursor.execute(f"SELECT COUNT(*) as total FROM olt{where_sql}", params)
    total_items = cursor.fetchone()['total']
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE) if total_items > 0 else 1

    final_params = params + [ITEMS_PER_PAGE, offset]
    cursor.execute(f"SELECT * FROM olt{where_sql} ORDER BY id_olt DESC LIMIT %s OFFSET %s", final_params)
    olts = cursor.fetchall()
    cursor.close()
    conn.close()

    start_item = offset + 1 if total_items > 0 else 0
    end_item = offset + len(olts)
    
    pagination_data = {
        'current_page': page, 'total_pages': total_pages, 'total_items': total_items,
        'start_item': start_item, 'end_item': end_item,
        'iter_pages': [p for p in range(max(1, page - 2), min(total_pages, page + 2) + 1)]
    }
    
    return render_template('olt_list.html', olts=olts, pagination=pagination_data, search=search_query)

@app.route('/olts/add', methods=['GET', 'POST'])
@login_required 
def olt_add():
    if request.method == 'POST':
        nama = request.form['nama_olt']
        pon = request.form['pon_olt']
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # CEK APAKAH NAMA OLT SUDAH ADA
        cursor.execute("SELECT id_olt FROM olt WHERE nama_olt = %s", (nama,))
        if cursor.fetchone():
            flash('Error: Nama OLT sudah ada, silakan gunakan nama lain.', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('olt_add'))

        # Jika tidak ada, lanjutkan INSERT
        cursor.execute("INSERT INTO olt (nama_olt, pon_olt) VALUES (%s, %s)", (nama, pon))
        conn.commit()
        cursor.close()
        conn.close()
        flash('OLT baru berhasil ditambahkan!', 'success')
        return redirect(url_for('olt_list'))

    return render_template('olt_form.html', action='add', olt=None)

@app.route('/olts/edit/<int:id>', methods=['GET', 'POST'])
@login_required 
def olt_edit(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        nama = request.form['nama_olt']
        pon = request.form['pon_olt']
        
        # CEK APAKAH NAMA OLT SUDAH DIPAKAI OLEH OLT LAIN
        cursor.execute("SELECT id_olt FROM olt WHERE nama_olt = %s AND id_olt != %s", (nama, id))
        if cursor.fetchone():
            flash('Error: Nama OLT tersebut sudah digunakan oleh OLT lain.', 'danger')
            cursor.close()
            conn.close()
            return redirect(url_for('olt_edit', id=id))
        
        # Jika tidak ada, lanjutkan UPDATE
        update_cursor = conn.cursor()
        update_cursor.execute("UPDATE olt SET nama_olt=%s, pon_olt=%s WHERE id_olt=%s", (nama, pon, id))
        conn.commit()
        update_cursor.close()
        flash('Data OLT berhasil diperbarui!', 'success')
        return redirect(url_for('olt_list'))
    
    # Bagian GET tidak berubah
    cursor.execute("SELECT * FROM olt WHERE id_olt=%s", (id,))
    olt = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('olt_form.html', action='edit', olt=olt)

@app.route('/olts/delete/<int:id>', methods=['POST'])
@login_required 
def olt_delete(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM olt WHERE id_olt=%s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('OLT berhasil dihapus!', 'danger')
    return redirect(url_for('olt_list'))

# =================================================================
# === CRUD UNTUK ODC (Optical Distribution Cabinet) ===============
# =================================================================
@app.route('/odcs')
def odc_list():
    """Menampilkan data ODC dengan paginasi dan pencarian (VERSI DIPERBAIKI)."""
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()
    ITEMS_PER_PAGE = 10
    offset = (page - 1) * ITEMS_PER_PAGE

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    params = []
    where_clauses = [] # Mulai dengan list kosong

    # HANYA JIKA ADA PENCARIAN, kita tambahkan klausa dan parameter
    if search_query:
        where_clauses.append("(nama_odc LIKE %s OR port_odc LIKE %s)")
        search_term = f"%{search_query}%"
        params.extend([search_term, search_term])

    # Bangun string SQL FINAL di sini. Jika where_clauses kosong, where_sql juga akan kosong.
    # Ini adalah KUNCI untuk mencegah error.
    where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    # Sekarang, `where_sql` dan `params` selalu sinkron.
    # Query hitung total akan valid baik dengan atau tanpa pencarian.
    cursor.execute(f"SELECT COUNT(*) as total FROM odc{where_sql}", params)
    total_items = cursor.fetchone()['total']
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE) if total_items > 0 else 1

    # Query ambil data juga akan selalu valid.
    final_params = params + [ITEMS_PER_PAGE, offset]
    cursor.execute(f"SELECT * FROM odc{where_sql} ORDER BY id_odc DESC LIMIT %s OFFSET %s", final_params)
    odcs = cursor.fetchall()
    cursor.close()
    conn.close()

    start_item = offset + 1 if total_items > 0 else 0
    end_item = offset + len(odcs)
    
    pagination_data = {
        'current_page': page, 'total_pages': total_pages, 'total_items': total_items,
        'start_item': start_item, 'end_item': end_item,
        'iter_pages': [p for p in range(max(1, page - 2), min(total_pages, page + 2) + 1)]
    }
    
    return render_template('odc_list.html', odcs=odcs, pagination=pagination_data, search=search_query)

@app.route('/odcs/add', methods=['GET', 'POST'])
@login_required 
def odc_add():
    if request.method == 'POST':
        nama = request.form['nama_odc']
        port = request.form['port_odc']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id_odc FROM odc WHERE nama_odc = %s", (nama,))
        if cursor.fetchone():
            flash('Error: Nama ODC sudah ada.', 'danger')
            return redirect(url_for('odc_add'))
        
        cursor.execute("INSERT INTO odc (nama_odc, port_odc) VALUES (%s, %s)", (nama, port))
        conn.commit()
        cursor.close()
        conn.close()
        flash('ODC baru berhasil ditambahkan!', 'success')
        return redirect(url_for('odc_list'))
    return render_template('odc_form.html', action='add', odc=None)

@app.route('/odcs/edit/<int:id>', methods=['GET', 'POST'])
@login_required 
def odc_edit(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        nama = request.form['nama_odc']
        port = request.form['port_odc']
        
        cursor.execute("SELECT id_odc FROM odc WHERE nama_odc = %s AND id_odc != %s", (nama, id))
        if cursor.fetchone():
            flash('Error: Nama ODC tersebut sudah digunakan.', 'danger')
            return redirect(url_for('odc_edit', id=id))

        update_cursor = conn.cursor()
        update_cursor.execute("UPDATE odc SET nama_odc=%s, port_odc=%s WHERE id_odc=%s", (nama, port, id))
        conn.commit()
        update_cursor.close()
        flash('Data ODC berhasil diperbarui!', 'success')
        return redirect(url_for('odc_list'))
    
    cursor.execute("SELECT * FROM odc WHERE id_odc=%s", (id,))
    odc = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('odc_form.html', action='edit', odc=odc)

@app.route('/odcs/delete/<int:id>', methods=['POST'])
@login_required 
def odc_delete(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM odc WHERE id_odc=%s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('ODC berhasil dihapus!', 'danger')
    return redirect(url_for('odc_list'))

# =================================================================
# === CRUD UNTUK ODP (Optical Distribution Point) =================
# =================================================================
@app.route('/odps')
def odp_list():
    """Menampilkan data ODP dengan paginasi dan pencarian."""
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()
    ITEMS_PER_PAGE = 10
    offset = (page - 1) * ITEMS_PER_PAGE

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    params = []
    where_clauses = []
    if search_query:
        where_clauses.append("(nama_odp LIKE %s OR alamat_odp LIKE %s)")
        search_term = f"%{search_query}%"
        params.extend([search_term, search_term])
    
    where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    cursor.execute(f"SELECT COUNT(*) as total FROM odp{where_sql}", params)
    total_items = cursor.fetchone()['total']
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE) if total_items > 0 else 1

    final_params = params + [ITEMS_PER_PAGE, offset]
    cursor.execute(f"SELECT * FROM odp{where_sql} ORDER BY id_odp DESC LIMIT %s OFFSET %s", final_params)
    odps = cursor.fetchall()
    cursor.close()
    conn.close()

    start_item = offset + 1 if total_items > 0 else 0
    end_item = offset + len(odps)
    
    pagination_data = {
        'current_page': page, 'total_pages': total_pages, 'total_items': total_items,
        'start_item': start_item, 'end_item': end_item,
        'iter_pages': [p for p in range(max(1, page - 2), min(total_pages, page + 2) + 1)]
    }
    
    return render_template('odp_list.html', odps=odps, pagination=pagination_data, search=search_query)

@app.route('/odps/add', methods=['GET', 'POST'])
@login_required
def odp_add():
    if request.method == 'POST':
        # Ambil data sebagai list dari form
        list_nama = request.form.getlist('nama_odp[]')
        list_alamat = request.form.getlist('alamat_odp[]')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        successful_inserts = 0
        failed_entries = []
        processed_names = set()

        # Loop melalui setiap baris data yang disubmit
        for i in range(len(list_nama)):
            nama = list_nama[i].strip()
            alamat = list_alamat[i].strip()

            # Lewati baris jika nama ODP kosong
            if not nama:
                continue
            
            # Cek duplikat di dalam batch yang sama
            if nama in processed_names:
                failed_entries.append(f"Nama ODP '{nama}': Duplikat dalam batch.")
                continue

            # Cek duplikat di database
            cursor.execute("SELECT id_odp FROM odp WHERE nama_odp = %s", (nama,))
            if cursor.fetchone():
                failed_entries.append(f"Nama ODP '{nama}': sudah ada di database.")
                continue

            # Jika semua validasi lolos, masukkan ke database
            try:
                sql = "INSERT INTO odp (nama_odp, alamat_odp) VALUES (%s, %s)"
                cursor.execute(sql, (nama, alamat))
                successful_inserts += 1
                processed_names.add(nama) # Tandai nama ini sudah diproses
            except Exception as e:
                failed_entries.append(f"'{nama}': Gagal disimpan ({e})")

        conn.commit()
        cursor.close()
        conn.close()

        if successful_inserts > 0:
            flash(f'{successful_inserts} ODP baru berhasil ditambahkan!', 'success')
        if failed_entries:
            flash(f'Beberapa data gagal ditambahkan: {"; ".join(failed_entries)}', 'danger')

        return redirect(url_for('odp_list'))

    # Untuk method GET, tampilkan halaman form batch
    return render_template('odp_form_add.html')

@app.route('/odps/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def odp_edit(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        # Logika edit untuk satu data tidak berubah
        nama = request.form['nama_odp']
        alamat = request.form['alamat_odp']
        
        cursor.execute("SELECT id_odp FROM odp WHERE nama_odp = %s AND id_odp != %s", (nama, id))
        if cursor.fetchone():
            flash('Error: Nama ODP tersebut sudah digunakan.', 'danger')
            return redirect(url_for('odp_edit', id=id))

        update_cursor = conn.cursor()
        update_cursor.execute("UPDATE odp SET nama_odp=%s, alamat_odp=%s WHERE id_odp=%s", (nama, alamat, id))
        conn.commit()
        update_cursor.close()
        flash('Data ODP berhasil diperbarui!', 'success')
        return redirect(url_for('odp_list'))
    
    # Bagian GET request, panggil template 'edit' yang sudah kita siapkan
    cursor.execute("SELECT * FROM odp WHERE id_odp=%s", (id,))
    odp = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('odp_form_edit.html', odp=odp)

@app.route('/odps/delete/<int:id>', methods=['POST'])
@login_required 
def odp_delete(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM odp WHERE id_odp=%s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('ODP berhasil dihapus!', 'danger')
    return redirect(url_for('odp_list'))

# =================================================================
# === CRUD UNTUK RINCIAN ODP ======================================
# =================================================================
# =================================================================
# === CRUD UNTUK RINCIAN ODP (VERSI BARU DENGAN FAT) ==============
# =================================================================

@app.route('/details/odp')
def rincian_odp_list():
    """Menampilkan daftar jalur ODP dengan fitur filter dan paginasi."""
    
    # LANGKAH 1: Ambil input dari pengguna (filter dan halaman)
    page = request.args.get('page', 1, type=int)
    selected_fat = request.args.get('fat', '')
    selected_olt = request.args.get('olt', '')
    selected_odc = request.args.get('odc', '')
    selected_odp = request.args.get('odp', '')

    # LANGKAH 2: Siapkan variabel paginasi
    ITEMS_PER_PAGE = 10
    offset = (page - 1) * ITEMS_PER_PAGE

    # --- MEMBANGUN QUERY DINAMIS ---
    base_from_sql = """
        FROM rincian_odp ro
        JOIN fat f ON ro.id_fat = f.id_fat
        JOIN olt o ON ro.id_olt = o.id_olt
        JOIN odc od ON ro.id_odc = od.id_odc
        JOIN odp p ON ro.id_odp = p.id_odp
    """
    
    params = []
    where_clauses = []

    # LANGKAH 3: Buat daftar kondisi WHERE berdasarkan filter
    if selected_fat:
        where_clauses.append("ro.id_fat = %s"); params.append(selected_fat)
    if selected_olt:
        where_clauses.append("ro.id_olt = %s"); params.append(selected_olt)
    if selected_odc:
        where_clauses.append("ro.id_odc = %s"); params.append(selected_odc)
    if selected_odp:
        where_clauses.append("ro.id_odp = %s"); params.append(selected_odp)

    where_sql = ""
    if where_clauses:
        where_sql = " WHERE " + " AND ".join(where_clauses)
        
    # --- EKSEKUSI QUERY ---
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # LANGKAH 4: Query PERTAMA untuk menghitung TOTAL item yang sesuai filter
    count_sql = f"SELECT COUNT(*) as total {base_from_sql}{where_sql}"
    cursor.execute(count_sql, params)
    total_items = cursor.fetchone()['total']
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE) if total_items > 0 else 1

    # LANGKAH 5: Query KEDUA untuk mengambil data per halaman
    data_sql = f"""
        SELECT 
            ro.id_rodp, f.nama_fat, o.nama_olt, o.pon_olt, o.status_pon,
            od.nama_odc, od.port_odc, p.nama_odp, ro.warna_kabel,
            -- Subquery untuk menghitung total client per ODP
            (SELECT COUNT(*) FROM rincian_client rc JOIN rincian_odp ro_inner ON rc.id_rodp = ro_inner.id_rodp WHERE ro_inner.id_odp = p.id_odp) as client_count
        {base_from_sql}{where_sql}
        ORDER BY ro.id_rodp DESC
        LIMIT %s OFFSET %s
    """
    final_params = params + [ITEMS_PER_PAGE, offset]
    cursor.execute(data_sql, final_params)
    rincian_list = cursor.fetchall()

    cursor.close()
    conn.close()

    # --- PERSIAPAN DATA UNTUK DIKIRIM KE TEMPLATE ---
    master_data = get_all_master_data()
    current_filters = {
        'fat': selected_fat, 'olt': selected_olt, 
        'odc': selected_odc, 'odp': selected_odp
    }
    
    start_item = offset + 1 if total_items > 0 else 0
    end_item = offset + len(rincian_list)
    
    pagination_data = {
        'current_page': page,
        'total_pages': total_pages,
        'total_items': total_items,
        'start_item': start_item,
        'end_item': end_item,
        'iter_pages': [p for p in range(max(1, page - 2), min(total_pages, page + 2) + 1)]
    }

    return render_template(
        'rincian_odp_list.html', 
        rincian_list=rincian_list,
        master_data=master_data,
        filters=current_filters,
        pagination=pagination_data
    )

def get_all_master_data():
    """Mengambil semua data dari tabel master untuk filter dropdown."""
    master_data = {}
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT id_fat, nama_fat FROM fat ORDER BY nama_fat")
        master_data['fats'] = cursor.fetchall()
        
        cursor.execute("SELECT id_olt, nama_olt, pon_olt FROM olt ORDER BY nama_olt")
        master_data['olts'] = cursor.fetchall()
        
        cursor.execute("SELECT id_odc, nama_odc, port_odc FROM odc ORDER BY nama_odc")
        master_data['odcs'] = cursor.fetchall()
        
        cursor.execute("SELECT id_odp, nama_odp FROM odp ORDER BY nama_odp")
        master_data['odps'] = cursor.fetchall()
    
    finally:
        cursor.close()
        conn.close()
        
    return master_data

def get_master_data_for_rodp():
    """Helper function untuk mengambil data FAT, OLT, ODC, ODP untuk form."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
       # Pastikan pon_olt (yang sekarang berisi angka) diambil
    cursor.execute("SELECT id_olt, nama_olt, pon_olt FROM olt ORDER BY nama_olt")
    olts = cursor.fetchall()
    cursor.execute("SELECT id_fat, nama_fat FROM fat ORDER BY nama_fat")
    fats = cursor.fetchall()
    cursor.execute("SELECT id_olt, nama_olt, pon_olt FROM olt ORDER BY nama_olt")
    olts = cursor.fetchall()
    cursor.execute("SELECT id_odc, nama_odc, port_odc FROM odc ORDER BY nama_odc")
    odcs = cursor.fetchall()
    cursor.execute("SELECT id_odp, nama_odp FROM odp ORDER BY nama_odp")
    odps = cursor.fetchall()
    cursor.close()
    conn.close()
    # Kembalikan fats sebagai nilai pertama
    return fats, olts, odcs, odps

# Ganti fungsi rincian_odp_add Anda dengan ini
# Ganti fungsi rincian_odp_add Anda dengan ini
@app.route('/details/odp/add', methods=['GET', 'POST'])
@login_required 
def rincian_odp_add():
    if request.method == 'POST':
        # Ambil data sebagai list (tanpa pon_port)
        list_id_fat = request.form.getlist('id_fat[]')
        list_id_olt = request.form.getlist('id_olt[]')
        list_id_odc = request.form.getlist('id_odc[]')
        list_id_odp = request.form.getlist('id_odp[]')
        list_warna_kabel = request.form.getlist('warna_kabel[]')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        successful_inserts = 0
        failed_entries = []

        # Loop melalui setiap baris data
        for i in range(len(list_id_fat)):
            id_odp = list_id_odp[i]
            if not id_odp:
                continue

            # Validasi duplikat ODP
            cursor.execute("SELECT id_rodp FROM rincian_odp WHERE id_odp = %s", (id_odp,))
            if cursor.fetchone():
                failed_entries.append(f"Baris {i+1}: ODP sudah terdaftar di jalur lain.")
                continue

            try:
                # INSERT tanpa pon_port
                sql = "INSERT INTO rincian_odp (id_fat, id_olt, id_odc, id_odp, warna_kabel) VALUES (%s, %s, %s, %s, %s)"
                params = (list_id_fat[i], list_id_olt[i], list_id_odc[i], id_odp, list_warna_kabel[i])
                cursor.execute(sql, params)
                successful_inserts += 1
            except Exception as e:
                failed_entries.append(f"Baris {i+1}: Gagal disimpan ({e})")
        
        conn.commit()
        cursor.close()
        conn.close()

        if successful_inserts > 0:
            flash(f'{successful_inserts} jalur baru berhasil ditambahkan!', 'success')
        if failed_entries:
            flash(f'Beberapa jalur gagal ditambahkan: {"; ".join(failed_entries)}', 'danger')
        
        return redirect(url_for('rincian_odp_list'))

    fats, olts, odcs, odps = get_master_data_for_rodp() 
    return render_template('rincian_odp_form_add.html', action='add', fats=fats, olts=olts, odcs=odcs, odps=odps)

# Ganti fungsi rincian_odp_edit Anda dengan ini
@app.route('/details/odp/edit/<int:id>', methods=['GET', 'POST'])
@login_required 
def rincian_odp_edit(id):
    conn = get_db_connection()
    if request.method == 'POST':
        # Ambil data form tanpa pon_port
        id_fat = request.form['id_fat']
        id_olt = request.form['id_olt']
        id_odc = request.form['id_odc']
        id_odp = request.form['id_odp']
        warna_kabel = request.form['warna_kabel']

        cursor = conn.cursor(dictionary=True)
        
        check_sql = "SELECT id_rodp FROM rincian_odp WHERE id_odp = %s AND id_rodp != %s"
        cursor.execute(check_sql, (id_odp, id))
        if cursor.fetchone():
            flash('Error: ODP tersebut sudah terdaftar di jalur lain!', 'danger')
            return redirect(url_for('rincian_odp_edit', id=id))

        update_cursor = conn.cursor()
        # UPDATE tanpa pon_port
        update_sql = "UPDATE rincian_odp SET id_fat=%s, id_olt=%s, id_odc=%s, id_odp=%s, warna_kabel=%s WHERE id_rodp=%s"
        update_cursor.execute(update_sql, (id_fat, id_olt, id_odc, id_odp, warna_kabel, id))
        conn.commit()
        update_cursor.close()
        
        flash('Rincian ODP berhasil diperbarui!', 'success')
        return redirect(url_for('rincian_odp_list'))

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM rincian_odp WHERE id_rodp = %s", (id,))
    rincian = cursor.fetchone()
    
    # Fungsi get_master_data_for_rodp sekarang tidak lagi perlu info port
    fats, olts, odcs, odps = get_master_data_for_rodp()
    
    cursor.close()
    conn.close()
    
    return render_template('rincian_odp_form_edit.html', action='edit', rincian=rincian, fats=fats, olts=olts, odcs=odcs, odps=odps)

# Fungsi delete tidak perlu diubah
@app.route('/details/odp/delete/<int:id>', methods=['POST'])
@login_required 
def rincian_odp_delete(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM rincian_odp WHERE id_rodp = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Rincian ODP berhasil dihapus!', 'danger')
    return redirect(url_for('rincian_odp_list'))


# =================================================================
# === CRUD UNTUK RINCIAN CLIENT ===================================
# =================================================================

@app.route('/details/client')
def rincian_client_list():
    """Menampilkan daftar client dengan fitur filter, pencarian, dan paginasi (VERSI DIPERBAIKI)."""
    
    # LANGKAH 1: Ambil semua input dari pengguna (filter, search, dan halaman)
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()
    selected_fat = request.args.get('fat', '')
    selected_olt = request.args.get('olt', '')
    selected_odc = request.args.get('odc', '')
    selected_odp = request.args.get('odp', '')

    # LANGKAH 2: Siapkan variabel untuk paginasi
    ITEMS_PER_PAGE = 10
    offset = (page - 1) * ITEMS_PER_PAGE

    # --- MEMBANGUN QUERY SECARA DINAMIS (BAGIAN UTAMA) ---
    
    # Definisikan bagian FROM...JOIN... sekali saja agar tidak berulang
    base_from_sql = """
        FROM rincian_client rc
        JOIN client c ON rc.id_client = c.id_client
        JOIN rincian_odp ro ON rc.id_rodp = ro.id_rodp
        JOIN fat f ON ro.id_fat = f.id_fat
        JOIN olt o ON ro.id_olt = o.id_olt
        JOIN odc od ON ro.id_odc = od.id_odc
        JOIN odp p ON ro.id_odp = p.id_odp
    """
    
    params = []
    where_clauses = []

    # LANGKAH 3: Buat daftar kondisi WHERE berdasarkan input pengguna
    # Tambahkan kondisi untuk PENCARIAN
    if search_query:
        where_clauses.append("(c.nama_client LIKE %s OR c.nomor_telp LIKE %s OR c.ip_address LIKE %s)")
        search_term = f"%{search_query}%"
        params.extend([search_term, search_term, search_term])

    # Tambahkan kondisi untuk FILTER
    if selected_fat:
        where_clauses.append("ro.id_fat = %s")
        params.append(selected_fat)
    if selected_olt:
        where_clauses.append("ro.id_olt = %s")
        params.append(selected_olt)
    if selected_odc:
        where_clauses.append("ro.id_odc = %s")
        params.append(selected_odc)
    if selected_odp:
        where_clauses.append("ro.id_odp = %s")
        params.append(selected_odp)

    # Gabungkan semua kondisi WHERE jika ada
    where_sql = ""
    if where_clauses:
        where_sql = " WHERE " + " AND ".join(where_clauses)
        
    # --- EKSEKUSI QUERY ---
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # LANGKAH 4: Jalankan Query PERTAMA untuk menghitung TOTAL item yang sesuai filter
    count_sql = f"SELECT COUNT(*) as total {base_from_sql}{where_sql}"
    cursor.execute(count_sql, params)
    total_items = cursor.fetchone()['total']
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE) if total_items > 0 else 1

    # LANGKAH 5: Jalankan Query KEDUA untuk mengambil data per halaman
    data_sql = f"""
        SELECT 
            rc.id_rclient, c.nama_client, c.alamat_client, c.nomor_telp,
            f.nama_fat, o.nama_olt, o.pon_olt, od.nama_odc, od.port_odc, p.nama_odp, ro.warna_kabel
        {base_from_sql}{where_sql}
        ORDER BY c.nama_client ASC
        LIMIT %s OFFSET %s
    """
    # Tambahkan parameter untuk LIMIT dan OFFSET ke daftar params
    final_params = params + [ITEMS_PER_PAGE, offset]
    cursor.execute(data_sql, final_params)
    rincian_list = cursor.fetchall()

    cursor.close()
    conn.close()

    # --- PERSIAPAN DATA UNTUK DIKIRIM KE TEMPLATE ---
    master_data = get_all_master_data()
    current_filters = {
        'search': search_query, 'fat': selected_fat, 'olt': selected_olt, 
        'odc': selected_odc, 'odp': selected_odp
    }
    
    start_item = offset + 1 if total_items > 0 else 0
    end_item = offset + len(rincian_list)
    
    pagination_data = {
        'current_page': page,
        'total_pages': total_pages,
        'total_items': total_items,
        'start_item': start_item,
        'end_item': end_item,
        'iter_pages': [p for p in range(max(1, page - 2), min(total_pages, page + 2) + 1)]
    }
    
    return render_template(
        'rincian_client_list.html', 
        rincian_list=rincian_list, 
        master_data=master_data,
        filters=current_filters,
        pagination=pagination_data
    )

def get_master_data_for_rclient():
    """Helper untuk mengambil data Client dan Rincian ODP (dengan FAT) untuk form."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id_client, nama_client, ip_address FROM client ORDER BY nama_client")
    clients = cursor.fetchall()
    
    # Buat deskripsi yang jelas untuk setiap jalur ODP, TERMASUK FAT
    sql_rodp = """
        SELECT 
            ro.id_rodp, f.nama_fat, o.nama_olt, od.nama_odc, p.nama_odp, ro.warna_kabel,
            -- Subquery untuk menghitung total client yang sudah terhubung ke ODP dari jalur ini
            (SELECT COUNT(*) 
             FROM rincian_client rc 
             JOIN rincian_odp ro_inner ON rc.id_rodp = ro_inner.id_rodp 
             WHERE ro_inner.id_odp = p.id_odp) as client_count
        FROM rincian_odp ro
        JOIN fat f ON ro.id_fat = f.id_fat
        JOIN olt o ON ro.id_olt = o.id_olt
        JOIN odc od ON ro.id_odc = od.id_odc
        JOIN odp p ON ro.id_odp = p.id_odp
        ORDER BY ro.id_rodp DESC
    """
    cursor.execute(sql_rodp)
    rincian_odps_raw = cursor.fetchall()
    
    rincian_odps = []
    for r in rincian_odps_raw:
        count = r['client_count']
        deskripsi = f" ODP: {r['nama_odp']} | Area: {r['nama_fat']} (Terisi: {count} Client)"
        rincian_odps.append({'id_rodp': r['id_rodp'], 'deskripsi': deskripsi})

    cursor.close()
    conn.close()
    return clients, rincian_odps

# Ganti fungsi rincian_client_add Anda dengan ini
@app.route('/details/client/add', methods=['GET', 'POST'])
@login_required 
def rincian_client_add():
    if request.method == 'POST':
        list_id_client = request.form.getlist('id_client[]')
        list_id_rodp = request.form.getlist('id_rodp[]')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        successful_inserts = 0
        failed_entries = []

        for i in range(len(list_id_client)):
            id_client = list_id_client[i]
            id_rodp = list_id_rodp[i]

            if not id_client or not id_rodp:
                continue
            
            cursor.execute("SELECT id_rclient FROM rincian_client WHERE id_client = %s", (id_client,))
            if cursor.fetchone():
                failed_entries.append(f"Client ID {id_client}: sudah terhubung.")
                continue

            try:
                sql = "INSERT INTO rincian_client (id_rodp, id_client) VALUES (%s, %s)"
                cursor.execute(sql, (id_rodp, id_client))
                successful_inserts += 1
            except Exception as e:
                 failed_entries.append(f"Client ID {id_client}: Gagal disimpan ({e})")

        conn.commit()
        cursor.close()
        conn.close()

        if successful_inserts > 0:
            flash(f'{successful_inserts} koneksi client baru berhasil ditambahkan!', 'success')
        if failed_entries:
            flash(f'Beberapa koneksi gagal ditambahkan: {"; ".join(failed_entries)}', 'danger')
        
        return redirect(url_for('rincian_client_list'))

    clients, rincian_odps = get_master_data_for_rclient()
    return render_template('rincian_client_form_add.html', action='add', clients=clients, rincian_odps=rincian_odps)


# Ganti fungsi rincian_client_edit Anda dengan ini
@app.route('/details/client/edit/<int:id>', methods=['GET', 'POST'])
@login_required 
def rincian_client_edit(id):
    conn = get_db_connection()
    if request.method == 'POST':
        # Logika edit tidak berubah
        id_rodp = request.form['id_rodp']
        id_client = request.form['id_client']

        cursor = conn.cursor(dictionary=True)
        
        check_sql = "SELECT id_rclient FROM rincian_client WHERE id_client = %s AND id_rclient != %s"
        cursor.execute(check_sql, (id_client, id))
        if cursor.fetchone():
            flash('Error: Client tersebut sudah terhubung di jalur lain. Pilih client yang berbeda.', 'danger')
            return redirect(url_for('rincian_client_edit', id=id))

        update_cursor = conn.cursor()
        update_sql = "UPDATE rincian_client SET id_rodp=%s, id_client=%s WHERE id_rclient=%s"
        update_cursor.execute(update_sql, (id_rodp, id_client, id))
        conn.commit()
        update_cursor.close()

        flash('Rincian koneksi client berhasil diperbarui!', 'success')
        return redirect(url_for('rincian_client_list'))
        
    # Panggil template edit
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM rincian_client WHERE id_rclient = %s", (id,))
    rincian = cursor.fetchone()
    
    clients, rincian_odps = get_master_data_for_rclient()
    
    cursor.close()
    conn.close()

    return render_template('rincian_client_form_edit.html', action='edit', rincian=rincian, clients=clients, rincian_odps=rincian_odps)


@app.route('/details/client/delete/<int:id>', methods=['POST'])
@login_required 
def rincian_client_delete(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM rincian_client WHERE id_rclient = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Koneksi client berhasil dihapus!', 'danger')
    return redirect(url_for('rincian_client_list'))

# =================================================================
# === CRUD UNTUK FAT (Fiber Access Terminal / Area) ===============
# =================================================================
@app.route('/fats')
def fat_list():
    """Menampilkan data FAT dengan paginasi dan pencarian."""
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '').strip()
    ITEMS_PER_PAGE = 10
    offset = (page - 1) * ITEMS_PER_PAGE

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    params = []
    where_sql = ""
    if search_query:
        where_sql = " WHERE nama_fat LIKE %s"
        params.append(f"%{search_query}%")

    cursor.execute(f"SELECT COUNT(*) as total FROM fat{where_sql}", params)
    total_items = cursor.fetchone()['total']
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE) if total_items > 0 else 1

    final_params = params + [ITEMS_PER_PAGE, offset]
    cursor.execute(f"SELECT * FROM fat{where_sql} ORDER BY id_fat DESC LIMIT %s OFFSET %s", final_params)
    fats = cursor.fetchall()
    cursor.close()
    conn.close()

    start_item = offset + 1 if total_items > 0 else 0
    end_item = offset + len(fats)
    
    pagination_data = {
        'current_page': page, 'total_pages': total_pages, 'total_items': total_items,
        'start_item': start_item, 'end_item': end_item,
        'iter_pages': [p for p in range(max(1, page - 2), min(total_pages, page + 2) + 1)]
    }
    
    return render_template('fat_list.html', fats=fats, pagination=pagination_data, search=search_query)

@app.route('/fats/add', methods=['GET', 'POST'])
@login_required 
def fat_add():
    if request.method == 'POST':
        nama = request.form['nama_fat']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id_fat FROM fat WHERE nama_fat = %s", (nama,))
        if cursor.fetchone():
            flash('Error: Nama FAT / Area sudah ada.', 'danger')
            return redirect(url_for('fat_add'))

        cursor.execute("INSERT INTO fat (nama_fat) VALUES (%s)", (nama,))
        conn.commit()
        cursor.close()
        conn.close()
        flash('FAT / Area baru berhasil ditambahkan!', 'success')
        return redirect(url_for('fat_list'))
    return render_template('fat_form.html', action='add', fat=None)

@app.route('/fats/edit/<int:id>', methods=['GET', 'POST'])
@login_required 
def fat_edit(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        nama = request.form['nama_fat']
        
        cursor.execute("SELECT id_fat FROM fat WHERE nama_fat = %s AND id_fat != %s", (nama, id))
        if cursor.fetchone():
            flash('Error: Nama FAT / Area tersebut sudah digunakan.', 'danger')
            return redirect(url_for('fat_edit', id=id))
        
        update_cursor = conn.cursor()
        update_cursor.execute("UPDATE fat SET nama_fat=%s WHERE id_fat=%s", (nama, id))
        conn.commit()
        update_cursor.close()
        flash('Data FAT / Area berhasil diperbarui!', 'success')
        return redirect(url_for('fat_list'))
    
    cursor.execute("SELECT * FROM fat WHERE id_fat=%s", (id,))
    fat = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('fat_form.html', action='edit', fat=fat)

@app.route('/fats/delete/<int:id>', methods=['POST'])
@login_required 
def fat_delete(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM fat WHERE id_fat=%s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash('FAT / Area berhasil dihapus!', 'danger')
    return redirect(url_for('fat_list'))

def add_log(action, details=""):
    """Fungsi helper untuk menambahkan log aktivitas."""
    try:
        # Hanya catat jika ada pengguna yang login
        if 'logged_in' in session:
            username = session.get('username', 'N/A')
            conn = get_db_connection()
            cursor = conn.cursor()
            sql = "INSERT INTO activity_logs (username, action, details) VALUES (%s, %s, %s)"
            cursor.execute(sql, (username, action, details))
            conn.commit()
            cursor.close()
            conn.close()
    except Exception as e:
        # Jika logging gagal, jangan sampai menghentikan aplikasi utama
        print(f"Error saat menambahkan log: {e}")

@app.route('/logs')
@superadmin_required
@login_required
def activity_logs():
    """Menampilkan halaman log aktivitas dengan paginasi."""
    page = request.args.get('page', 1, type=int)
    ITEMS_PER_PAGE = 20 # Log bisa lebih banyak per halaman
    offset = (page - 1) * ITEMS_PER_PAGE

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) as total FROM activity_logs")
    total_items = cursor.fetchone()['total']
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE) if total_items > 0 else 1

    cursor.execute("SELECT * FROM activity_logs ORDER BY timestamp DESC LIMIT %s OFFSET %s", (ITEMS_PER_PAGE, offset))
    logs = cursor.fetchall()
    
    cursor.close()
    conn.close()

    pagination_data = {
        'current_page': page, 'total_pages': total_pages, 'total_items': total_items,
        'start_item': offset + 1 if total_items > 0 else 0, 'end_item': offset + len(logs),
        'iter_pages': [p for p in range(max(1, page - 2), min(total_pages, page + 2) + 1)]
    }

    return render_template('logs.html', logs=logs, pagination=pagination_data)

@app.route('/export/clients')
@login_required
def export_clients():
    """Mengekspor data rincian client yang terfilter ke CSV (VERSI DIPERBAIKI)."""
    
    # ... (Bagian pengambilan parameter filter tidak berubah) ...
    search_query = request.args.get('search', '').strip()
    selected_fat = request.args.get('fat', '')
    selected_olt = request.args.get('olt', '')
    selected_odc = request.args.get('odc', '')
    selected_odp = request.args.get('odp', '')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ... (Bagian pembangunan query 'WHERE' tidak berubah) ...
    params = []
    where_clauses = []
    base_from_sql = """
        FROM rincian_client rc
        JOIN client c ON rc.id_client = c.id_client
        JOIN rincian_odp ro ON rc.id_rodp = ro.id_rodp
        JOIN fat f ON ro.id_fat = f.id_fat
        JOIN olt o ON ro.id_olt = o.id_olt
        JOIN odc od ON ro.id_odc = od.id_odc
        JOIN odp p ON ro.id_odp = p.id_odp
    """
    if search_query:
        where_clauses.append("(c.nama_client LIKE %s OR c.nomor_telp LIKE %s OR c.ip_address LIKE %s)")
        search_term = f"%{search_query}%"
        params.extend([search_term, search_term, search_term])
    if selected_fat:
        where_clauses.append("f.id_fat = %s"); params.append(selected_fat)
    if selected_olt:
        where_clauses.append("o.id_olt = %s"); params.append(selected_olt)
    if selected_odc:
        where_clauses.append("od.id_odc = %s"); params.append(selected_odc)
    if selected_odp:
        where_clauses.append("p.id_odp = %s"); params.append(selected_odp)
    where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""


    # --- PERUBAHAN DI SINI ---
    # Buat query SELECT LENGKAP, tapi TANPA ro.pon_port
    final_sql = f"""
        SELECT 
            c.nama_client as 'Nama Client',
            c.alamat_client as 'Alamat',
            c.nomor_telp as 'Nomor Telepon',
            c.ip_address as 'IP Address',
            f.nama_fat as 'Area (FAT)',
            o.nama_olt as 'OLT',
            o.pon_olt as 'PON',
            od.nama_odc as 'ODC',
            od.port_odc as 'ODC PORT',
            p.nama_odp as 'ODP',
            ro.warna_kabel as 'Warna Kabel'
        {base_from_sql}{where_sql} 
        ORDER BY c.nama_client ASC
    """
    
    cursor.execute(final_sql, params)
    data_to_export = cursor.fetchall()
    cursor.close()
    conn.close()

    # ... (Bagian Pandas untuk membuat CSV tidak berubah) ...
    if not data_to_export:
        flash("Tidak ada data untuk diekspor sesuai filter yang dipilih.", "warning")
        return redirect(url_for('rincian_client_list', **request.args))
        
    df = pd.DataFrame(data_to_export)
    
    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)

    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=laporan_rincian_client.csv"}
    )

@app.route('/export/rincian_odp')
@login_required
def export_rincian_odp():
    """Mengekspor data rincian ODP yang terfilter ke CSV."""
    
    # 1. Ambil semua parameter filter dari URL
    selected_fat = request.args.get('fat', '')
    selected_olt = request.args.get('olt', '')
    selected_odc = request.args.get('odc', '')
    selected_odp = request.args.get('odp', '')

    # 2. Bangun query dinamis (logika disalin dari rincian_odp_list)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    params = []
    where_clauses = []
    base_from_sql = """
        FROM rincian_odp ro
        JOIN fat f ON ro.id_fat = f.id_fat
        JOIN olt o ON ro.id_olt = o.id_olt
        JOIN odc od ON ro.id_odc = od.id_odc
        JOIN odp p ON ro.id_odp = p.id_odp
    """
    
    if selected_fat:
        where_clauses.append("ro.id_fat = %s"); params.append(selected_fat)
    if selected_olt:
        where_clauses.append("ro.id_olt = %s"); params.append(selected_olt)
    if selected_odc:
        where_clauses.append("ro.id_odc = %s"); params.append(selected_odc)
    if selected_odp:
        where_clauses.append("ro.id_odp = %s"); params.append(selected_odp)

    where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    # 3. Buat query SELECT LENGKAP, tapi TANPA LIMIT/OFFSET
    final_sql = f"""
        SELECT 
            f.nama_fat as 'Area (FAT)',
            o.nama_olt as 'OLT',
            o.pon_olt as 'Info PON OLT',
            od.nama_odc as 'ODC',
            od.port_odc as 'Info Port ODC',
            p.nama_odp as 'ODP',
            ro.warna_kabel as 'Warna Kabel'
        {base_from_sql}{where_sql} 
        ORDER BY ro.id_rodp DESC
    """
    
    cursor.execute(final_sql, params)
    data_to_export = cursor.fetchall()
    cursor.close()
    conn.close()

    # 4. Gunakan Pandas untuk membuat CSV jika ada data
    if not data_to_export:
        flash("Tidak ada data untuk diekspor sesuai filter yang dipilih.", "warning")
        return redirect(url_for('rincian_odp_list', **request.args))
        
    df = pd.DataFrame(data_to_export)
    
    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)

    # 5. Kirim sebagai file download ke browser
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=laporan_jalur_odp.csv"}
    )

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/tools/isolir', methods=['GET', 'POST'])
@superadmin_required
@login_required
def tool_isolir_batch():
    if request.method == 'POST':
        if 'excel_file' not in request.files:
            flash('Tidak ada file yang dipilih.', 'danger')
            return redirect(request.url)
        
        file = request.files['excel_file']
        if file.filename == '':
            flash('Tidak ada file yang dipilih.', 'danger')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            try:
                df = pd.read_excel(file, header=1)
                # ... (kode validasi kolom PPOE tetap sama) ...

                ip_list = df["PPOE"].dropna().astype(str).tolist()
                
                # JANGAN JALANKAN PROSES DI SINI
                # Sebagai gantinya, buat ID tugas unik dan mulai thread
                task_id = str(uuid.uuid4())
                tasks[task_id] = {
                    'status': 'pending',
                    'progress': 0,
                    'total': len(ip_list),
                    'results': []
                }
                
                # Mulai tugas di thread baru
                thread = threading.Thread(target=run_isolir_task, args=(task_id, ip_list))
                thread.start()
                
                # Langsung arahkan ke halaman progress
                return redirect(url_for('isolir_progress', task_id=task_id))

            except Exception as e:
                flash(f"Terjadi error saat memproses file: {e}", "danger")
                return redirect(request.url)

    return render_template('tool_isolir_upload.html')

@app.route('/tools/isolir/progress/<task_id>')
@superadmin_required
@login_required
def isolir_progress(task_id):
    """Menampilkan halaman progress untuk sebuah tugas."""
    if task_id not in tasks:
        flash("Tugas tidak ditemukan.", "danger")
        return redirect(url_for('tool_isolir_batch'))
    return render_template('tool_isolir_progress.html', task_id=task_id)


@app.route('/tools/isolir/status/<task_id>')
@superadmin_required
@login_required
def isolir_status(task_id):
    """API endpoint untuk memberikan status tugas dalam format JSON."""
    if task_id not in tasks:
        return {"status": "error", "message": "Tugas tidak ditemukan."}
    
    task_data = tasks.get(task_id, {})
    return jsonify(task_data)

# Tambahkan fungsi baru ini
@app.route('/api/traffic/interface/<path:interface_name>')
@login_required
def api_get_interface_traffic(interface_name):
    """API untuk mengambil total traffic dari satu interface di MikroTik."""
    
    # Daftar endpoint interface dari semua router Anda
    router_endpoints = [
        f"https://{ROUTER_KPUTIH}/rest/interface",
        f"https://{ROUTER_KIT}/rest/interface"
    ]

    # Loop melalui setiap router untuk mencari interface
    for endpoint in router_endpoints:
        interfaces = get_mikrotik_api_data(endpoint)
        
        if interfaces:
            for iface in interfaces:
                if iface.get('name') == interface_name:
                    # Jika ketemu, langsung kirim datanya dan hentikan fungsi
                    return jsonify({
                        'name': iface.get('name'),
                        'rx_byte': int(iface.get('rx-byte', 0)),
                        'tx_byte': int(iface.get('tx-byte', 0))
                    })
    
    # Jika loop selesai dan interface tidak ditemukan, kirim error
    return jsonify({"error": f"Interface '{interface_name}' tidak ditemukan di router manapun."}), 404

def get_mikrotik_api_data(base_url):
    """Mengambil data dari endpoint API MikroTik tertentu."""
    try:
        response = requests.get(base_url, auth=HTTPBasicAuth(USERNAME_MIKROTIK, PASSWORD_MIKROTIK), verify=False, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error saat menghubungi {base_url}: {e}")
        return None

# Tambahkan fungsi ini di bagian FUNGSI HELPER UNTUK API MIKROTIK
def get_binding_details(ip_address):
    """Mengambil detail lengkap (id, comment, disabled) dari sebuah IP Binding."""
    # Hapus "static@" jika ada
    ip_address = ip_address.replace("static@", "")
    
    base_url, lokasi = get_router_info_by_ip(ip_address)
    if not base_url:
        return {'ip': ip_address, 'status': 'Tidak Dikenali', 'comment': '-', 'id': None, 'base_url': None}

    all_bindings = get_mikrotik_api_data(base_url)
    if all_bindings is None:
        return {'ip': ip_address, 'status': 'Router Tidak Terjangkau', 'comment': '-', 'id': None, 'base_url': base_url}

    for binding in all_bindings:
        if binding.get('address') == ip_address:
            is_disabled = binding.get('disabled') == 'true'
            return {
                'ip': ip_address,
                'status': 'Sudah Diisolir' if is_disabled else 'Aktif',
                'comment': binding.get('comment', 'Tanpa Nama'),
                'id': binding.get('.id'),
                'base_url': base_url
            }
            
    return {'ip': ip_address, 'status': 'Tidak Ditemukan', 'comment': '-', 'id': None, 'base_url': base_url}


# Fungsi yang berjalan di latar belakang untuk mengecek IP
def run_check_task(task_id, ip_list):
    """Tugas latar belakang untuk mengecek setiap IP dan mengambil detailnya."""
    tasks[task_id]['status'] = 'processing'
    preview_results = []
    
    for i, ip in enumerate(ip_list):
        detail = get_binding_details(ip)
        preview_results.append(detail)
        
        with threading.Lock():
            task_data = copy.deepcopy(tasks[task_id])
            task_data['progress'] = i + 1
            task_data['results'].append(f"Mengecek {ip}... Ditemukan: {detail['comment']} (Status: {detail['status']})")
            tasks[task_id] = task_data
        time.sleep(0.1)

    with threading.Lock():
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['preview_data'] = preview_results

# Route utama untuk form input
@app.route('/isolir', methods=['GET', 'POST'])
@login_required
@special_access_required
def isolir_tool():
    if request.method == 'POST':
        ip_list_raw = request.form.getlist('ip_address[]')
        ip_list = [ip.strip() for ip in ip_list_raw if ip.strip()]

        if not ip_list:
            flash("Silakan masukkan setidaknya satu alamat IP.", "warning")
            return redirect(url_for('isolir_tool'))

        task_id = str(uuid.uuid4())
        tasks[task_id] = {'type': 'checking', 'status': 'pending', 'progress': 0, 'total': len(ip_list), 'results': []}
        
        thread = threading.Thread(target=run_check_task, args=(task_id, ip_list))
        thread.start()
        add_log("Mulai Pengecekan IP Isolir", f"{len(ip_list)} IP dalam antrian. Task ID: {task_id}")
        return redirect(url_for('isolir_progresss', task_id=task_id))

    return render_template('isolir_form.html')

# Route untuk halaman progress
@app.route('/isolir/progress/<task_id>')
@login_required
@special_access_required
def isolir_progresss(task_id):
    if task_id not in tasks:
        flash("Tugas tidak ditemukan atau sudah kedaluwarsa.", "danger")
        return redirect(url_for('isolir_tool'))
    return render_template('isolir_progress.html', task_id=task_id)

# Route API untuk status
@app.route('/api/isolir/status/<task_id>')
@login_required
def isolir_statuss(task_id):
    task_data = tasks.get(task_id, {})
    if not task_data:
        return jsonify({"status": "error", "message": "Tugas tidak ditemukan."})
    return jsonify(task_data)

# Route untuk eksekusi final
@app.route('/isolir/execute', methods=['POST'])
@login_required
@special_access_required
def execute_isolir():
    items_to_isolir = request.form.getlist('to_isolate')
    
    if not items_to_isolir:
        flash("Tidak ada client yang dipilih untuk diisolir.", "warning")
        return redirect(url_for('isolir_tool'))

    success_count = 0
    failed_count = 0
    
    for item in items_to_isolir:
        try:
            binding_id, base_url, comment, ip = item.split('|')
            if set_binding_status(base_url, binding_id, disable=True):
                success_count += 1
                add_log("Eksekusi Isolir", f"Binding ID: {binding_id}, Nama: {comment}")
            else:
                failed_count += 1
        except Exception as e:
            failed_count += 1
            print(f"Error saat eksekusi isolir: {e}")

    flash(f"Proses isolir selesai. Berhasil: {success_count} client. Gagal: {failed_count} client.", "success" if failed_count == 0 else "warning")
    return redirect(url_for('isolir_tool'))

# Error Handler untuk 404 Not Found
@app.errorhandler(404)
def page_not_found(e):
    # e adalah objek error, kita tidak perlu menggunakannya tapi harus ada
    return render_template('404.html'), 404

# Error Handler untuk 500 Internal Server Error
@app.errorhandler(500)
def internal_server_error(e):
    # Di aplikasi production, di sini adalah tempat yang baik untuk mengirim notifikasi error
    # ke email admin atau sistem logging, tapi untuk sekarang cukup tampilkan halaman.
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(debug=True)