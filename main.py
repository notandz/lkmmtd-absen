import bcrypt
from flask import Flask, render_template, request, redirect, session
import mysql.connector
from flask import jsonify
import time
from datetime import datetime
from datetime import date
import pandas as pd
from io import BytesIO
from flask import send_file, make_response



app = Flask(__name__)
app.secret_key = 'papakilo1945randomwiuw'  # Kunci rahasia untuk sesi

db_config = {
    'host': '109.106.252.6',
    'user': 'u1571400_lkmm',
    'password': '@Jenuine123',
    'database': 'u1571400_lkmm'
}
    
mysql = mysql.connector.connect(**db_config)

# Maksimum waktu dalam detik sebelum pengguna otomatis logout
MAX_SESSION_TIME = 900  # 15 menit


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cur = mysql.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()

        if user and bcrypt.checkpw(password.encode('utf-8'), user[2].encode('utf-8')):
            session['username'] = user[1]
            session['login_time'] = time.time()

            role = user[3]  # Fetch the role value from the user record in MySQL

            if role == 1:
                session['role'] = 'admin'
                return redirect('/dashboard')  # Redirect to admin dashboard
            else:
                session['role'] = 'user'
                return redirect('/attendance')  # Redirect to user attendance page

        error = 'Invalid username or password. Please try again.'
        return render_template('login.html', error=error)

    return render_template('login.html')

@app.route('/attendance')
def attendance():
    # Periksa apakah pengguna telah terautentikasi
    if 'username' in session:
        # Periksa waktu login terakhir
        login_time = session.get('login_time')
        if login_time is not None and (time.time() - login_time) > MAX_SESSION_TIME:
            # Jika waktu login telah melewati batas waktu maksimum, logout pengguna
            return redirect('/logout')

        # Hitung sisa waktu sebelum logout
        current_time = time.time()
        remaining_time = int(MAX_SESSION_TIME - (current_time - login_time))

        return render_template('attendance.html', username=session['username'], timeout=remaining_time)

    # Jika pengguna belum terautentikasi, arahkan kembali ke halaman login
    return redirect('/')

@app.route('/dashboard')
def dashboard():
    if 'username' in session and session['role'] == 'admin':
        # Mendapatkan tanggal hari ini
        current_date = date.today()

        # Mengambil data pengguna yang login pada hari tersebut dari tabel attendance
        cur = mysql.cursor()
        cur.execute("SELECT username, timestamp, verified FROM attendance WHERE DATE(timestamp) = %s", (current_date,))
        login_data = cur.fetchall()
        cur.close()

        return render_template('dashboard.html', login_data=login_data)
    else:
        return redirect('/')
    
@app.route('/verify', methods=['POST'])
def verify():
    if 'username' in session and session['role'] == 'admin':
        username = request.form['username']
        timestamp = request.form['timestamp']
        verified = request.form['verified']

        cur = mysql.cursor()
        cur.execute("UPDATE attendance SET verified = %s WHERE username = %s AND timestamp = %s", (verified, username, timestamp))
        mysql.connection.commit()
        cur.close()

        return jsonify(message="Verifikasi berhasil.")

    return jsonify(error="Akses ditolak.")

@app.route('/logout')
def logout():
    # Hapus semua informasi sesi pengguna
    session.pop('username', None)
    session.pop('login_time', None)
    return redirect('/')

@app.route('/absen', methods=['POST'])
def absen():
    # Mendapatkan username dari sesi
    username = session.get('username')

    if username:
        # Mendapatkan waktu saat ini
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Pemeriksaan apakah pengguna telah melakukan absen pada hari yang sama sebelumnya
        cur = mysql.cursor()
        cur.execute("SELECT * FROM attendance WHERE username = %s AND DATE(timestamp) = %s", (username, date.today()))
        result = cur.fetchone()

        if result:
            # Jika pengguna telah melakukan absen pada hari yang sama, kembalikan pesan kesalahan
            return jsonify(error="Anda telah melakukan absen pada hari ini.")

        # Menyimpan data absen ke dalam tabel attendance
        cur.execute("INSERT INTO attendance (username, timestamp) VALUES (%s, %s)", (username, current_time))
        mysql.connection.commit()
        cur.close()

        # Mengembalikan respons berhasil dalam format JSON
        message = f"Absen berhasil. Username: {username}, Waktu: {current_time}"
        return jsonify(message=message)
    else:
        # Jika tidak ada sesi pengguna, kembalikan pesan kesalahan dalam format JSON
        return jsonify(error="Terjadi kesalahan. Silakan login kembali.")
    
@app.route('/download')
def download():
    if 'username' in session and session['role'] == 'admin':
        # Mendapatkan tanggal hari ini
        current_date = date.today()

        # Mengambil data pengguna yang login pada hari tersebut dari tabel attendance
        cur = mysql.cursor()
        cur.execute("SELECT username, timestamp, verifiedFROM attendance WHERE DATE(timestamp) = %s", (current_date,))
        login_data = cur.fetchall()
        cur.close()

        # Membuat DataFrame dari data yang diambil
        df = pd.DataFrame(login_data, columns=['Username', 'Timestamp', 'Verified'])

        # Membuat file Excel menggunakan pandas
        buffer = BytesIO()
        writer = pd.ExcelWriter(buffer, engine='openpyxl')
        df.to_excel(writer, index=False, sheet_name='Attendance')
        writer.save()
        buffer.seek(0)

        # Mengubah buffer ke respons file
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-Disposition'] = 'attachment; filename=attendance.xlsx'

        return response

    return redirect('/')

@app.route('/add_user', methods=['POST'])
def add_user():
    # Hanya admin yang dapat menambahkan user
    if 'username' in session and session['role'] == 'admin':
        username = request.form['username']
        password = request.form['password']
        role = int(request.form['role'])

        cur = mysql.cursor()
        # Periksa apakah username sudah terdaftar
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()

        if user:
            # Jika username sudah terdaftar, kirim pesan error
            return jsonify(message="User sudah terdaftar.")

        # Hash password menggunakan bcrypt
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Tambahkan user baru ke tabel users
        cur.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", (username, hashed_password, role))
        mysql.connection.commit()
        cur.close()

        # Kirim pesan sukses
        return jsonify(message="User berhasil ditambahkan.")
    
    # Jika bukan admin, kirim pesan error
    return jsonify(error="Akses ditolak.")


if __name__ == '__main__':
    app.run(debug=True)
