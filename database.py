import sqlite3
from datetime import datetime, timedelta
import bcrypt

DB_NAME = "users.db"

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            subscription_status TEXT DEFAULT 'FREE',
            expiry_date TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def register_user(username: str, email: str, password: str):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        pwd_hash = hash_password(password)
        expiry = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, subscription_status, expiry_date, created_at)
            VALUES (?, ?, ?, 'PRO_TRIAL', ?, ?)
        """, (username.strip(), email.strip().lower(), pwd_hash, expiry, created))
        conn.commit()
        return True, "सफलतापूर्वक अकाउंट बन गया! आपको 7 दिन का Pro ट्रायल मिला है।"
    except sqlite3.IntegrityError:
        return False, "यह Username या Email पहले से मौजूद है।"
    finally:
        conn.close()

def authenticate_user(email_or_user: str, password: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, email, password_hash, subscription_status, expiry_date 
        FROM users 
        WHERE email = ? OR username = ?
    """, (email_or_user.strip().lower(), email_or_user.strip()))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        return False, None, "यूज़रनेम या ईमेल नहीं मिला।"
    
    user_id, u_name, email, pwd_hash, status, expiry = user
    if check_password(password, pwd_hash):
        is_active = True
        if expiry:
            exp_dt = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
            if datetime.now() > exp_dt:
                is_active = False
                status = "EXPIRED"
        user_data = {
            "id": user_id,
            "username": u_name,
            "email": email,
            "status": status,
            "expiry": expiry,
            "is_active_pro": (is_active and status in ['PRO', 'VIP', 'PRO_TRIAL'])
        }
        return True, user_data, "लॉगिन सफल!"
    else:
        return False, None, "गलत पासवर्ड।"

init_db()
