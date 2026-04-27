import os
from flask import Blueprint, render_template, send_from_directory, current_app, flash, redirect, request
from flask_login import login_required
from models import get_db

bp = Blueprint('public', __name__)

@bp.route('/')
def index():
    return render_template('index.html')

@bp.route('/employer/<int:employer_id>')
def view_employer(employer_id):
    db = get_db()
    company = db.execute("SELECT * FROM employers WHERE user_id = ?", (employer_id,)).fetchone()
    if not company:
        return "Company not found", 404
        
    jobs = db.execute("SELECT * FROM jobs WHERE employer_id = ? AND status = 'verified' ORDER BY created_at DESC", (employer_id,)).fetchall()
    
    return render_template('view_employer_profile.html', company=company, jobs=jobs)

@bp.route('/resume/<filename>')
@login_required
def download_resume(filename):
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        flash("The resume file could not be found on the server. It may have been deleted.", "error")
        return redirect(request.referrer or '/')
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)
