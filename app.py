import os
import sqlite3
import psycopg2
import psycopg2.extras
from urllib.parse import urlparse
from flask import Flask, render_template, request, jsonify, send_file, session, redirect
from datetime import datetime, timedelta
import csv
import io
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import calendar
from functools import wraps

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

# ✅ Email Configuration
EMAIL_CONFIG = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'sender_email': 'your-email@gmail.com',      # Update this
    'sender_password': 'your-app-password',      # Update this
    'enable_emails': False                       # Set True after configuring
}


# ✅ Database connection helper
class DBAdapter:
    def __init__(self, conn, is_postgres=False):
        self.conn = conn
        self.is_postgres = is_postgres

    def execute(self, query, params=None):
        if self.is_postgres:
            # Handle PostgreSQL placeholder and keyword differences
            query = query.replace('?', '%s')
            # Handle AUTOINCREMENT -> SERIAL for table creation
            if 'AUTOINCREMENT' in query.upper():
                query = query.replace('AUTOINCREMENT', '')
                query = query.replace('INTEGER PRIMARY KEY', 'SERIAL PRIMARY KEY')
        
        cursor = self.conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor

    def cursor(self):
        return self.conn.cursor()

    def commit(self):
        return self.conn.commit()

    def close(self):
        return self.conn.close()

    def fetchone(self, cursor):
        return cursor.fetchone()

    def fetchall(self, cursor):
        return cursor.fetchall()

def get_db():
    database_url = os.getenv('DATABASE_URL')
    
    if database_url:
        # PostgreSQL connection (Vercel/Production)
        conn = psycopg2.connect(database_url, cursor_factory=psycopg2.extras.DictCursor)
        return DBAdapter(conn, is_postgres=True)
    else:
        # SQLite connection (Local Development)
        conn = sqlite3.connect('expense_manager.db')
        conn.row_factory = sqlite3.Row
        return DBAdapter(conn, is_postgres=False)


# ✅ Create tables if not exists
def init_db():
    conn = get_db()

    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            type TEXT NOT NULL,
            date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS recurring_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            type TEXT NOT NULL,
            frequency TEXT NOT NULL,
            next_date TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS email_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            weekly_reports BOOLEAN DEFAULT 0,
            budget_alerts BOOLEAN DEFAULT 0,
            monthly_summaries BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            theme_color TEXT DEFAULT '#0ea5ff',
            background_color TEXT DEFAULT '#eef2f3',
            card_color TEXT DEFAULT '#ffffff',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    conn.commit()
    conn.close()


# Initialize database
init_db()


# ✅ Helper function to hash passwords
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# ✅ Check if user is logged in
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Login required'}), 401
        return f(*args, **kwargs)
    return decorated_function


# ✅ Safe next date calculator
def calculate_next_date(current_date, frequency):
    current = datetime.strptime(current_date, '%Y-%m-%d')

    if frequency == 'weekly':
        return (current + timedelta(days=7)).strftime('%Y-%m-%d')

    elif frequency == 'monthly':
        year = current.year
        month = current.month + 1

        if month > 12:
            month = 1
            year += 1

        last_day = calendar.monthrange(year, month)[1]
        day = min(current.day, last_day)

        return datetime(year, month, day).strftime('%Y-%m-%d')

    elif frequency == 'yearly':
        year = current.year + 1
        month = current.month

        last_day = calendar.monthrange(year, month)[1]
        day = min(current.day, last_day)

        return datetime(year, month, day).strftime('%Y-%m-%d')

    else:
        return current_date


# ✅ Process recurring transactions safely
def process_recurring_transactions():
    conn = get_db()
    today = datetime.now().strftime('%Y-%m-%d')

    recurring = conn.execute('''
        SELECT * FROM recurring_transactions
        WHERE next_date <= ? AND is_active = 1
    ''', (today,)).fetchall()

    for recurring_tx in recurring:
        due_date = recurring_tx['next_date']

        conn.execute('''
            INSERT INTO transactions (user_id, title, amount, category, type, date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            recurring_tx['user_id'],
            recurring_tx['title'],
            recurring_tx['amount'],
            recurring_tx['category'],
            recurring_tx['type'],
            due_date
        ))

        next_date = calculate_next_date(due_date, recurring_tx['frequency'])

        while next_date <= today:
            next_date = calculate_next_date(next_date, recurring_tx['frequency'])

        conn.execute('''
            UPDATE recurring_transactions
            SET next_date = ?
            WHERE id = ?
        ''', (next_date, recurring_tx['id']))

    conn.commit()
    conn.close()


# ✅ Email sending function
def send_email(to_email, subject, html_content):
    if not EMAIL_CONFIG['enable_emails']:
        print(f"Email disabled. Would send to {to_email}: {subject}")
        return True

    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['sender_email']
        msg['To'] = to_email
        msg['Subject'] = subject

        msg.attach(MIMEText(html_content, 'html'))

        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()
        server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['sender_password'])

        text = msg.as_string()
        server.sendmail(EMAIL_CONFIG['sender_email'], to_email, text)
        server.quit()

        print(f"Email sent successfully to {to_email}")
        return True

    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


# ✅ Generate weekly report
def generate_weekly_report(user_id):
    conn = get_db()

    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        conn.close()
        return None

    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    transactions = conn.execute('''
        SELECT * FROM transactions
        WHERE user_id = ? AND date BETWEEN ? AND ?
        ORDER BY date DESC
    ''', (
        user_id,
        start_date.strftime('%Y-%m-%d'),
        end_date.strftime('%Y-%m-%d')
    )).fetchall()

    week_income = 0
    week_expense = 0
    category_breakdown = {}

    for tx in transactions:
        amount = tx['amount']
        if tx['type'] == 'income':
            week_income += amount
        else:
            week_expense += amount
            category = tx['category']
            category_breakdown[category] = category_breakdown.get(category, 0) + amount

    conn.close()

    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px; }}
            .stat-box {{ background: white; padding: 20px; margin: 10px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .income {{ border-left: 4px solid #10b981; }}
            .expense {{ border-left: 4px solid #ef4444; }}
            .category {{ display: flex; justify-content: space-between; margin: 5px 0; }}
            .tip {{ background: #eef2ff; padding: 15px; border-radius: 8px; margin: 15px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>💰 Your Weekly Expense Report</h1>
                <p>Hello {user['username']}! Here's your financial summary for the past week.</p>
            </div>

            <div class="content">
                <div class="stat-box income">
                    <h3>📈 Income This Week</h3>
                    <h2>₹{week_income:,.2f}</h2>
                </div>

                <div class="stat-box expense">
                    <h3>📉 Expenses This Week</h3>
                    <h2>₹{week_expense:,.2f}</h2>
                </div>

                <div class="stat-box">
                    <h3>⚖️ Weekly Balance</h3>
                    <h2 style="color: {'#10b981' if (week_income - week_expense) >= 0 else '#ef4444'}">
                        ₹{(week_income - week_expense):,.2f}
                    </h2>
                    <p>{'🎉 Great job! You saved money this week.' if (week_income - week_expense) >= 0 else '💡 Consider reviewing your expenses.'}</p>
                </div>

                <div class="stat-box">
                    <h3>📊 Spending by Category</h3>
                    {''.join([f'<div class="category"><span>{cat}</span><span>₹{amt:,.2f}</span></div>' for cat, amt in sorted(category_breakdown.items(), key=lambda x: x[1], reverse=True)]) if category_breakdown else '<p>No expenses this week.</p>'}
                </div>

                <div class="tip">
                    <h4>💡 Weekly Tip</h4>
                    <p>{"Try meal prepping to reduce food expenses!" if week_expense > week_income * 0.3 else "Great spending habits! Consider increasing your savings rate."}</p>
                </div>

                <p style="text-align: center; color: #666; margin-top: 30px;">
                    This report was generated automatically by your Expense Manager.<br>
                    <a href="http://localhost:5000">View Full Dashboard</a>
                </p>
            </div>
        </div>
    </body>
    </html>
    '''

    return {
        'subject': f'💰 Your Weekly Expense Report - {end_date.strftime("%b %d, %Y")}',
        'html_content': html_content,
        'user_email': user['email']
    }


# ✅ Send weekly reports to all users
def send_weekly_reports():
    if not EMAIL_CONFIG['enable_emails']:
        print("Email reports are disabled in configuration")
        return

    conn = get_db()

    users = conn.execute('''
        SELECT u.* FROM users u
        JOIN email_preferences ep ON u.id = ep.user_id
        WHERE ep.weekly_reports = 1
    ''').fetchall()

    for user in users:
        report = generate_weekly_report(user['id'])
        if report:
            threading.Thread(
                target=send_email,
                args=(report['user_email'], report['subject'], report['html_content'])
            ).start()

    conn.close()
    print(f"Scheduled weekly reports for {len(users)} users")


# ✅ Home Route
@app.route("/")
def home():
    if 'user_id' in session:
        return redirect('/dashboard')
    return render_template("landing.html")


@app.route("/dashboard")
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    process_recurring_transactions()
    return render_template("index.html")


# ✅ Login Page
@app.route("/login")
def login_page():
    if 'user_id' in session:
        return redirect('/dashboard')
    return render_template("login.html")


# ✅ Signup Page
@app.route("/signup")
def signup_page():
    if 'user_id' in session:
        return redirect('/dashboard')
    return render_template("signup.html")


# ✅ Login API
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    conn = get_db()
    user = conn.execute(
        'SELECT * FROM users WHERE username = ?', (username,)
    ).fetchone()
    conn.close()

    if user and user['password_hash'] == hash_password(password):
        session['user_id'] = user['id']
        session['username'] = user['username']
        return jsonify({"message": "Login successful", "username": user['username']})
    else:
        return jsonify({"error": "Invalid credentials"}), 401


# ✅ Signup API
@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return jsonify({"error": "All fields are required"}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
            (username, email, hash_password(password))
        )
        conn.commit()

        user = conn.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()

        conn.execute(
            'INSERT INTO email_preferences (user_id) VALUES (?)',
            (user['id'],)
        )
        conn.execute(
            'INSERT INTO user_preferences (user_id) VALUES (?)',
            (user['id'],)
        )
        conn.commit()

        session['user_id'] = user['id']
        session['username'] = user['username']

        conn.close()
        return jsonify({"message": "Signup successful", "username": username})

    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "Username or email already exists"}), 400


# ✅ Logout
@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logout successful"})


# ✅ Get user preferences
@app.route("/api/user-preferences", methods=["GET"])
@login_required
def get_user_preferences():
    conn = get_db()
    preferences = conn.execute(
        'SELECT * FROM user_preferences WHERE user_id = ?',
        (session['user_id'],)
    ).fetchone()
    conn.close()

    if preferences:
        return jsonify(dict(preferences))
    else:
        default_prefs = {
            'theme_color': '#0ea5ff',
            'background_color': '#eef2f3',
            'card_color': '#ffffff'
        }

        conn = get_db()
        conn.execute(
            'INSERT INTO user_preferences (user_id, theme_color, background_color, card_color) VALUES (?, ?, ?, ?)',
            (
                session['user_id'],
                default_prefs['theme_color'],
                default_prefs['background_color'],
                default_prefs['card_color']
            )
        )
        conn.commit()
        conn.close()

        return jsonify(default_prefs)


# ✅ Update user preferences
@app.route("/api/user-preferences", methods=["PUT"])
@login_required
def update_user_preferences():
    data = request.json

    conn = get_db()
    existing = conn.execute(
        'SELECT * FROM user_preferences WHERE user_id = ?',
        (session['user_id'],)
    ).fetchone()

    if existing:
        conn.execute('''
            UPDATE user_preferences
            SET theme_color = ?, background_color = ?, card_color = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', (
            data.get('theme_color', '#0ea5ff'),
            data.get('background_color', '#eef2f3'),
            data.get('card_color', '#ffffff'),
            session['user_id']
        ))
    else:
        conn.execute('''
            INSERT INTO user_preferences (user_id, theme_color, background_color, card_color)
            VALUES (?, ?, ?, ?)
        ''', (
            session['user_id'],
            data.get('theme_color', '#0ea5ff'),
            data.get('background_color', '#eef2f3'),
            data.get('card_color', '#ffffff')
        ))

    conn.commit()
    conn.close()

    return jsonify({"message": "Preferences updated successfully!"})


# ✅ Reset to default colors
@app.route("/api/user-preferences/reset", methods=["POST"])
@login_required
def reset_user_preferences():
    default_prefs = {
        'theme_color': '#0ea5ff',
        'background_color': '#eef2f3',
        'card_color': '#ffffff'
    }

    conn = get_db()
    conn.execute('''
        UPDATE user_preferences
        SET theme_color = ?, background_color = ?, card_color = ?, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
    ''', (
        default_prefs['theme_color'],
        default_prefs['background_color'],
        default_prefs['card_color'],
        session['user_id']
    ))
    conn.commit()
    conn.close()

    return jsonify({"message": "Preferences reset to default!", "preferences": default_prefs})


# ✅ Get email preferences
@app.route("/api/email-preferences", methods=["GET"])
@login_required
def get_email_preferences():
    conn = get_db()
    preferences = conn.execute(
        'SELECT * FROM email_preferences WHERE user_id = ?',
        (session['user_id'],)
    ).fetchone()
    conn.close()

    if preferences:
        return jsonify(dict(preferences))
    else:
        conn = get_db()
        conn.execute(
            'INSERT INTO email_preferences (user_id) VALUES (?)',
            (session['user_id'],)
        )
        conn.commit()
        conn.close()
        return jsonify({'weekly_reports': False, 'budget_alerts': False, 'monthly_summaries': False})


# ✅ Update email preferences
@app.route("/api/email-preferences", methods=["PUT"])
@login_required
def update_email_preferences():
    data = request.json

    conn = get_db()
    conn.execute('''
        UPDATE email_preferences
        SET weekly_reports = ?, budget_alerts = ?, monthly_summaries = ?
        WHERE user_id = ?
    ''', (
        data.get('weekly_reports', False),
        data.get('budget_alerts', False),
        data.get('monthly_summaries', False),
        session['user_id']
    ))
    conn.commit()
    conn.close()

    return jsonify({"message": "Email preferences updated successfully!"})


# ✅ Send test email
@app.route("/api/send-test-email", methods=["POST"])
@login_required
def send_test_email():
    conn = get_db()
    user = conn.execute(
        'SELECT * FROM users WHERE id = ?',
        (session['user_id'],)
    ).fetchone()
    conn.close()

    if not user:
        return jsonify({"error": "User not found"}), 404

    report = generate_weekly_report(session['user_id'])
    if report and send_email(user['email'], "Test Email from Expense Manager", report['html_content']):
        return jsonify({"message": "Test email sent successfully!"})
    else:
        return jsonify({"error": "Failed to send test email"}), 500


# ✅ Manual trigger for weekly reports
@app.route("/api/send-weekly-reports", methods=["POST"])
def manual_weekly_reports():
    send_weekly_reports()
    return jsonify({"message": "Weekly reports sent successfully!"})


# ✅ Fetch all transactions
@app.route("/transactions", methods=["GET"])
@login_required
def get_transactions():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM transactions WHERE user_id = ? ORDER BY date DESC",
        (session['user_id'],)
    )
    transactions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(transactions)


# ✅ Add a new transaction
@app.route("/add", methods=["POST"])
@login_required
def add_transaction():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()

    sql = "INSERT INTO transactions (user_id, title, amount, category, type, date) VALUES (?, ?, ?, ?, ?, ?)"
    values = (
        session['user_id'],
        data["title"],
        data["amount"],
        data["category"],
        data["type"],
        data["date"]
    )

    cursor.execute(sql, values)
    conn.commit()
    conn.close()

    return jsonify({"message": "Transaction added successfully!"})


# ✅ Add recurring transaction
@app.route("/api/recurring", methods=["POST"])
@login_required
def add_recurring_transaction():
    data = request.json

    conn = get_db()
    cursor = conn.cursor()

    sql = """
        INSERT INTO recurring_transactions
        (user_id, title, amount, category, type, frequency, next_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    values = (
        session['user_id'],
        data["title"],
        data["amount"],
        data["category"],
        data["type"],
        data["frequency"],
        data["next_date"]
    )

    cursor.execute(sql, values)
    conn.commit()
    conn.close()

    return jsonify({"message": "Recurring transaction added successfully!"})


# ✅ Get user's recurring transactions
@app.route("/api/recurring", methods=["GET"])
@login_required
def get_recurring_transactions():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM recurring_transactions WHERE user_id = ? ORDER BY next_date",
        (session['user_id'],)
    )
    recurring = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(recurring)


# ✅ Delete recurring transaction
@app.route("/api/recurring/<int:recurring_id>", methods=["DELETE"])
@login_required
def delete_recurring_transaction(recurring_id):
    conn = get_db()
    cursor = conn.cursor()

    recurring = cursor.execute(
        "SELECT * FROM recurring_transactions WHERE id = ? AND user_id = ?",
        (recurring_id, session['user_id'])
    ).fetchone()

    if not recurring:
        conn.close()
        return jsonify({"error": "Recurring transaction not found"}), 404

    cursor.execute("DELETE FROM recurring_transactions WHERE id = ?", (recurring_id,))
    conn.commit()
    conn.close()

    return jsonify({"message": "Recurring transaction deleted successfully!"})


# ✅ Toggle recurring transaction active status
@app.route("/api/recurring/<int:recurring_id>/toggle", methods=["PUT"])
@login_required
def toggle_recurring_transaction(recurring_id):
    conn = get_db()
    cursor = conn.cursor()

    recurring = cursor.execute(
        "SELECT * FROM recurring_transactions WHERE id = ? AND user_id = ?",
        (recurring_id, session['user_id'])
    ).fetchone()

    if not recurring:
        conn.close()
        return jsonify({"error": "Recurring transaction not found"}), 404

    new_status = 0 if recurring['is_active'] else 1
    cursor.execute(
        "UPDATE recurring_transactions SET is_active = ? WHERE id = ?",
        (new_status, recurring_id)
    )
    conn.commit()
    conn.close()

    return jsonify({"message": "Recurring transaction updated", "is_active": bool(new_status)})


# ✅ Edit a transaction
@app.route("/edit/<int:transaction_id>", methods=["PUT"])
@login_required
def edit_transaction(transaction_id):
    data = request.json
    conn = get_db()
    cursor = conn.cursor()

    transaction = cursor.execute(
        "SELECT * FROM transactions WHERE id = ? AND user_id = ?",
        (transaction_id, session['user_id'])
    ).fetchone()

    if not transaction:
        conn.close()
        return jsonify({"error": "Transaction not found"}), 404

    sql = "UPDATE transactions SET title=?, amount=?, category=?, type=?, date=? WHERE id=? AND user_id=?"
    values = (
        data["title"],
        data["amount"],
        data["category"],
        data["type"],
        data["date"],
        transaction_id,
        session['user_id']
    )

    cursor.execute(sql, values)
    conn.commit()
    conn.close()

    return jsonify({"message": "Transaction updated successfully!"})


# ✅ Delete a transaction
@app.route("/delete/<int:transaction_id>", methods=["DELETE"])
@login_required
def delete_transaction(transaction_id):
    conn = get_db()
    cursor = conn.cursor()

    transaction = cursor.execute(
        "SELECT * FROM transactions WHERE id = ? AND user_id = ?",
        (transaction_id, session['user_id'])
    ).fetchone()

    if not transaction:
        conn.close()
        return jsonify({"error": "Transaction not found"}), 404

    cursor.execute(
        "DELETE FROM transactions WHERE id = ? AND user_id = ?",
        (transaction_id, session['user_id'])
    )
    conn.commit()
    conn.close()

    return jsonify({"message": "Transaction deleted successfully!"})


# ✅ Get current user info
@app.route("/api/user")
@login_required
def get_user():
    return jsonify({
        "id": session['user_id'],
        "username": session['username']
    })


# ✅ AI Financial Coach Page
@app.route("/ai-coach")
@login_required
def ai_coach():
    return render_template("ai_coach.html")


# ✅ AI Coach — fetch real transaction context
@app.route("/ai-coach/context", methods=["GET"])
@login_required
def ai_coach_context():
    """Return the last 50 transactions + summary stats for the logged-in user."""
    conn = get_db()
    txs = conn.execute('''
        SELECT id, title, amount, category, type, date
        FROM transactions
        WHERE user_id = ?
        ORDER BY date DESC
        LIMIT 50
    ''', (session['user_id'],)).fetchall()
    conn.close()

    txs = [dict(t) for t in txs]

    total_income  = sum(t['amount'] for t in txs if t['type'] == 'income')
    total_expense = sum(t['amount'] for t in txs if t['type'] == 'expense')
    balance       = total_income - total_expense

    cat_breakdown = {}
    for t in txs:
        if t['type'] == 'expense':
            cat_breakdown[t['category']] = cat_breakdown.get(t['category'], 0) + t['amount']

    return jsonify({
        'transactions': txs,
        'total_income':  total_income,
        'total_expense': total_expense,
        'balance':       balance,
        'count':         len(txs),
        'cat_breakdown': cat_breakdown,
        'username':      session.get('username', 'User')
    })








# ✅ Tips Page
@app.route("/tips")
@login_required
def tips():
    return render_template("tips.html")


# ✅ Export all transactions to CSV
@app.route("/export_csv", methods=["GET"])
@login_required
def export_csv():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM transactions WHERE user_id = ? ORDER BY date DESC",
        (session['user_id'],)
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Title", "Amount", "Category", "Type", "Date"])

    for row in rows:
        writer.writerow([
            row["id"],
            row["title"],
            row["amount"],
            row["category"],
            row["type"],
            row["date"]
        ])

    output.seek(0)

    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="transactions.csv"
    )


# ✅ Run the app
if __name__ == "__main__":
    app.run(debug=True)
    