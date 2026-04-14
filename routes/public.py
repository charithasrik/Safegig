from flask import Blueprint, render_template, send_from_directory, current_app
from flask_login import login_required
from models import get_db

bp = Blueprint('public', __name__)

@bp.route('/')
def index():
    return render_template('index.html')

@bp.route('/articles')
def articles():
    db = get_db()
    articles_list = db.execute("SELECT * FROM articles ORDER BY created_at DESC").fetchall()
    return render_template('articles.html', articles=articles_list)

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
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)
