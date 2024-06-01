from flask import Flask, render_template, request, redirect, url_for, flash
from flask_socketio import SocketIO, emit
import sqlite3
from datetime import datetime, timedelta
import logging
import os
from dotenv import load_dotenv
from email_utils import send_email

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "your_default_secret_key")
socketio = SocketIO(app)

CAR_WASH_COMPANY_EMAIL = os.getenv("CAR_WASH_COMPANY_EMAIL", "carwash@shambles.no")
YOUR_EMAIL = os.getenv("YOUR_EMAIL", "your_email@example.com")
YOUR_PASSWORD = os.getenv("YOUR_PASSWORD", "your_password")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.example.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_database():
    with sqlite3.connect('carwash.db') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS car_wash_requests
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      license_plate TEXT,
                      name TEXT,
                      phone_number TEXT,
                      email TEXT,
                      exit_date TEXT,
                      product TEXT,
                      comments TEXT,
                      email_sent BOOLEAN DEFAULT 0,
                      washed BOOLEAN DEFAULT 0,
                      parked_location TEXT,
                      picked_up BOOLEAN DEFAULT 0,
                      carwash_pickup BOOLEAN DEFAULT 0,
                      request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()

create_database()

def add_car_wash_request(license_plate, name, phone_number, email, exit_date, product, comments):
    try:
        with sqlite3.connect('carwash.db') as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO car_wash_requests (license_plate, name, phone_number, email, exit_date, product, comments, email_sent) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (license_plate, name, phone_number, email, exit_date, product, comments, False))
            request_id = c.lastrowid
            conn.commit()
            return request_id
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        return None

def get_license_plate_by_id(request_id):
    with sqlite3.connect('carwash.db') as conn:
        c = conn.cursor()
        c.execute("SELECT license_plate FROM car_wash_requests WHERE id = ?", (request_id,))
        result = c.fetchone()
    return result[0] if result else None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/overview')
def overview():
    search = request.args.get('search')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    with sqlite3.connect('carwash.db') as conn:
        c = conn.cursor()

        queries = [
            ("requests", "SELECT * FROM car_wash_requests WHERE picked_up = 0 AND carwash_pickup = 0 AND washed = 0"),
            ("in_progress", "SELECT * FROM car_wash_requests WHERE carwash_pickup = 1 AND picked_up = 0 AND washed = 0"),
            ("ready", "SELECT * FROM car_wash_requests WHERE washed = 1 AND picked_up = 0")
        ]

        results = {}
        for key, base_query in queries:
            query = base_query
            params = []

            if search:
                query += " AND (license_plate LIKE ? OR name LIKE ?)"
                search_param = f"%{search}%"
                params.extend([search_param, search_param])

            if start_date:
                query += " AND DATE(request_date) >= DATE(?)"
                params.append(datetime.strptime(start_date, '%d/%m/%Y').strftime('%Y-%m-%d'))

            if end_date:
                query += " AND DATE(request_date) <= DATE(?)"
                params.append(datetime.strptime(end_date, '%d/%m/%Y').strftime('%Y-%m-%d'))

            c.execute(query, params)
            results[key] = c.fetchall()

        for key in ["requests", "in_progress"]:
            results[key].sort(key=lambda x: datetime.strptime(x[5], "%d/%m/%Y %H:%M"))

    return render_template('overview.html', **results)

@app.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        form_data = {
            'license_plate': request.form['license_plate'],
            'name': request.form['name'],
            'phone_number': request.form['phone_number'],
            'email': request.form['email'],
            'exit_date': request.form['exit_date'],
            'product': request.form['product'],
            'comments': request.form['comments']
        }
        add_lading = request.form.get('add_lading')

        if add_lading and form_data['product'] != "Lading":
            form_data['product'] += " + Lading"

        request_id = add_car_wash_request(**form_data)

        if request_id:
            subject = f"Ny bestilling for {form_data['license_plate']}"
            body = f"""
            Ny bestilling:

            Skilt Nummer: {form_data['license_plate']}
            Navn: {form_data['name']}
            Telefon Nummer: {form_data['phone_number']}
            Email Adresse: {form_data['email']}
            Utkjøring Dato og Tid: {form_data['exit_date']}
            Produkt: {form_data['product']}
            Kommentarer: {form_data['comments']}
            """

            if send_email(subject, body, CAR_WASH_COMPANY_EMAIL):
                with sqlite3.connect('carwash.db') as conn:
                    c = conn.cursor()
                    c.execute("UPDATE car_wash_requests SET email_sent = 1 WHERE id = ?", (request_id,))
                    conn.commit()
                logging.info(f"Database updated: email_sent set to 1 for request ID {request_id}")
                flash("Autofresh er kontaktet på mail, bestillingen finnes nå på oversikt.", "success")
            else:
                logging.warning(f"Failed to send email for request ID {request_id}")
                flash("Noe gikk galt, dobbeltsjekk at bestillingen er riktig lagt til og at Autofresh er informert.", "error")
        else:
            logging.error("Failed to add car wash request to database")
            flash("Noe gikk galt, dobbeltsjekk at bestillingen er riktig lagt til og at Autofresh er informert.", "error")

        return redirect(url_for('overview'))
    return render_template('add.html')

@app.route('/mark_carwash_pickup/<int:id>', methods=['POST'])
def mark_carwash_pickup(id):
    license_plate = get_license_plate_by_id(id)
    if license_plate:
        update_status(id, 'carwash_pickup', 1)
        flash(f"{license_plate} er hentet av Autofresh, {license_plate} ligger nå i oversikt over biler som er på vask.", "success")
    return redirect(url_for('overview'))

@app.route('/mark_washed/<int:id>', methods=['POST'])
def mark_washed(id):
    license_plate = get_license_plate_by_id(id)
    if license_plate:
        update_status(id, 'washed', 1)
        flash(f"{license_plate} er nå ferdigvasket, {license_plate} ligger nå i oversikt over biler som er klare til å hentes.", "success")
    return redirect(url_for('overview'))

@app.route('/mark_picked_up/<int:id>', methods=['POST'])
def mark_picked_up(id):
    license_plate = get_license_plate_by_id(id)
    if license_plate:
        update_status(id, 'picked_up', 1)
        flash(f"{license_plate} er nå hentet av kunde og fjernet fra oversikten.", "success")
    return redirect(url_for('overview'))


@app.route('/update_location/<int:id>', methods=['POST'])
def update_location(id):
    parked_location = request.form['parked_location']
    license_plate = get_license_plate_by_id(id)
    if license_plate:
        update_field(id, 'parked_location', parked_location)
        flash(f"{license_plate} er nå parkert på {parked_location}.", "success")
    return redirect(url_for('overview'))


def update_status(id, field, value):
    with sqlite3.connect('carwash.db') as conn:
        c = conn.cursor()
        c.execute(f"UPDATE car_wash_requests SET {field} = ? WHERE id = ?", (value, id))
        conn.commit()
    socketio.emit('update', {'msg': f'{field} updated'})

def update_field(id, field, value):
    with sqlite3.connect('carwash.db') as conn:
        c = conn.cursor()
        c.execute(f"UPDATE car_wash_requests SET {field} = ? WHERE id = ?", (value, id))
        conn.commit()
    socketio.emit('update', {'msg': 'Location updated'})

@app.route('/statistikk')
def statistikk():
    today = datetime.today().strftime('%Y-%m-%d')
    week_start = (datetime.today() - timedelta(days=datetime.today().weekday())).strftime('%Y-%m-%d')
    month_start = datetime.today().strftime('%Y-%m-01')
    year_start = datetime.today().strftime('%Y-01-01')

    with sqlite3.connect('carwash.db') as conn:
        c = conn.cursor()
        counts = {
            'daily_count': count_requests(c, today),
            'weekly_count': count_requests(c, week_start),
            'monthly_count': count_requests(c, month_start),
            'yearly_count': count_requests(c, year_start),
            'total_count': count_requests(c),
            'total_lading_count': count_requests(c, product_filter='%Lading%'),
            'total_vask_lading_count': count_requests(c, product_filter='%+ Lading%'),
            'daily_vask_lading_count': count_requests(c, today, '%+ Lading%'),
            'weekly_vask_lading_count': count_requests(c, week_start, '%+ Lading%'),
            'monthly_vask_lading_count': count_requests(c, month_start, '%+ Lading%'),
            'yearly_vask_lading_count': count_requests(c, year_start, '%+ Lading%'),
            'daily_lading_count': count_requests(c, today, 'Lading'),
            'weekly_lading_count': count_requests(c, week_start, 'Lading'),
            'monthly_lading_count': count_requests(c, month_start, 'Lading'),
            'yearly_lading_count': count_requests(c, year_start, 'Lading')
        }

    return render_template('statistikk.html', **counts)

def count_requests(cursor, date=None, product_filter=None):
    query = "SELECT COUNT(*) FROM car_wash_requests WHERE 1=1"
    params = []

    if date:
        query += " AND DATE(request_date) >= DATE(?)"
        params.append(date)

    if product_filter:
        query += " AND product LIKE ?"
        params.append(product_filter)

    cursor.execute(query, params)
    return cursor.fetchone()[0]

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', allow_unsafe_werkzeug=True)
