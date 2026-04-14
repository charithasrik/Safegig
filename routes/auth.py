from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
import re
from werkzeug.security import check_password_hash, generate_password_hash
from models import User, get_db
from flask import session
import random
from email_utils import send_otp_email, send_reset_link_email

bp = Blueprint('auth', __name__)

def is_strong_password(password):
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False
    return True

@bp.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'student')
        
        error = None
        if not username:
            error = 'Username is required.'
        elif not email:
            error = 'Email is required.'
        elif not password:
            error = 'Password is required.'
        elif not is_strong_password(password):
            error = 'Password must be at least 8 characters long, contain an uppercase letter, a lowercase letter, a number, and a special character.'
        elif role not in ['student', 'employer']:
            error = 'Invalid role selected.'

        if error is None:
            try:
                success = User.create(username, email, password, role)
                if success:
                    flash('Registration successful. Please log in.', 'success')
                    return redirect(url_for('auth.login'))
                else:
                    error = f"Username {username} or email {email} is already registered."
            except Exception as e:
                error = str(e)

        flash(error, 'error')

    return render_template('register.html')


@bp.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        error = None
        user_data = User.get_by_username(username)

        if user_data is None:
            import time; time.sleep(1) # Basic protection against brute force
            error = 'Incorrect username.'
        else:
            if not check_password_hash(user_data['password_hash'], password):
                import time; time.sleep(1)
                error = 'Incorrect password.'

        if error is None:
            user = User(
                id=user_data['id'],
                username=user_data['username'],
                email=user_data['email'],
                role=user_data['role']
            )
            login_user(user)
            if user.role == 'student':
                return redirect(url_for('student.dashboard'))
            elif user.role == 'employer':
                return redirect(url_for('employer.dashboard'))
            elif user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            else:
                return redirect(url_for('public.index'))

        flash(error, 'error')

    return render_template('login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('public.index'))

@bp.route('/forgot-password', methods=('GET', 'POST'))
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        
        if user:
            from itsdangerous import URLSafeTimedSerializer
            serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
            token = serializer.dumps(email, salt='password-reset-salt')
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            
            send_reset_link_email(email, reset_url)
            
        # We always say a link was sent to prevent email enumeration
        flash('If an account matches that email, a password reset link has been sent.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/forgot_password.html')

@bp.route('/reset-password/<token>', methods=('GET', 'POST'))
def reset_password(token):
    from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except (SignatureExpired, BadTimeSignature):
        flash('The password reset link is invalid or has expired.', 'error')
        return redirect(url_for('auth.forgot_password'))
        
    if request.method == 'POST':
        password = request.form.get('password')
        
        if not password or not is_strong_password(password):
            flash('Password must be at least 8 characters long, contain an uppercase letter, a lowercase letter, a number, and a special character.', 'error')
            return redirect(url_for('auth.reset_password', token=token))
            
        db = get_db()
        db.execute(
            "UPDATE users SET password_hash = ? WHERE email = ?",
            (generate_password_hash(password, method='scrypt:32768:8:1'), email)
        )
        db.execute("DELETE FROM password_resets WHERE email = ?", (email,))
        db.commit()
        
        flash('Your password has been securely reset. You can now log in.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/reset_password.html', token=token)
