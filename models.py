import psycopg2
import psycopg2.extras
from psycopg2 import IntegrityError
from flask import current_app, g
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

class PostgresCursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor
        
    def execute(self, query, params=None):
        query = query.replace('?', '%s')
        if params is not None:
             self.cursor.execute(query, params)
        else:
             self.cursor.execute(query)
        return self

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def close(self):
        self.cursor.close()
        
class PostgresConnectionWrapper:
    def __init__(self, conn):
        self.conn = conn
        
    def execute(self, query, params=None):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        wrapper = PostgresCursorWrapper(cur)
        wrapper.execute(query, params)
        return wrapper

    def executescript(self, script):
        cur = self.conn.cursor()
        cur.execute(script)
        self.conn.commit()

    def commit(self):
        self.conn.commit()
        
    def close(self):
        self.conn.close()

def get_db():
    if 'db' not in g:
        conn = psycopg2.connect(current_app.config['POSTGRES_URL'])
        g.db = PostgresConnectionWrapper(conn)
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    with current_app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf8'))
        
    # Create default admin
    db.execute(
        "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
        ('admin', 'admin@safegig.com', generate_password_hash('admin123'), 'admin')
    )
    db.commit()

# User Model for Flask-Login
class User(UserMixin):
    def __init__(self, id, username, email, role):
        self.id = id
        self.username = username
        self.email = email
        self.role = role

    @staticmethod
    def get(user_id):
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not user:
            return None
        return User(
            id=user['id'], username=user['username'], email=user['email'], role=user['role']
        )

    @staticmethod
    def get_by_username(username):
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not user:
            return None
        return user

    @staticmethod
    def create(username, email, password, role):
        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                (username, email, generate_password_hash(password, method='scrypt:32768:8:1'), role)
            )
            db.commit()
            return True
        except IntegrityError:
            return False
