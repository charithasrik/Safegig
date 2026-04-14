from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import get_db
from utils import role_required

bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.before_request
@role_required('admin')
def before_request():
    pass

@bp.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    page = request.args.get('page', 1, type=int)
    per_page = 5
    offset = (page - 1) * per_page
    
    pending_jobs = db.execute("SELECT j.*, e.company_name FROM jobs j JOIN employers e ON j.employer_id = e.user_id WHERE j.status = 'pending' ORDER BY j.created_at DESC LIMIT ? OFFSET ?", (per_page, offset)).fetchall()
    verified_jobs = db.execute("SELECT j.*, e.company_name FROM jobs j JOIN employers e ON j.employer_id = e.user_id WHERE j.status = 'verified' ORDER BY j.created_at DESC LIMIT 20").fetchall()
    rejected_jobs = db.execute("SELECT j.*, e.company_name FROM jobs j JOIN employers e ON j.employer_id = e.user_id WHERE j.status = 'rejected' ORDER BY j.created_at DESC LIMIT 20").fetchall()
    
    total_users = db.execute("SELECT COUNT(*) FROM users WHERE role != 'admin'").fetchone()[0]
    total_jobs = db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    
    total_pending = db.execute("SELECT COUNT(*) FROM jobs WHERE status = 'pending'").fetchone()[0]
    total_pages = (total_pending + per_page - 1) // per_page
    pending_approvals = total_pending
    
    return render_template('dashboard_admin.html', jobs=pending_jobs, verified_jobs=verified_jobs, rejected_jobs=rejected_jobs, total_users=total_users, total_jobs=total_jobs, pending_approvals=pending_approvals, page=page, total_pages=total_pages)

@bp.route('/verify/<int:job_id>', methods=['POST'])
@login_required
def verify_job(job_id):
    action = request.form.get('action')
    new_status = 'verified' if action == 'verify' else 'rejected'
    
    db = get_db()
    db.execute("UPDATE jobs SET status = ? WHERE id = ?", (new_status, job_id))
    db.commit()
    flash(f"Job {new_status}.", 'success')
    return redirect(url_for('admin.dashboard'))

@bp.route('/articles', methods=['GET', 'POST'])
@login_required
def manage_articles():
    db = get_db()
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        category = request.form['category']
        
        db.execute("INSERT INTO articles (title, content, category) VALUES (?, ?, ?)", (title, content, category))
        db.commit()
        flash('Article published.', 'success')
        return redirect(url_for('admin.manage_articles'))
        
    articles = db.execute("SELECT * FROM articles ORDER BY created_at DESC").fetchall()
    return render_template('admin_articles.html', articles=articles)

@bp.route('/users')
@login_required
def view_users():
    db = get_db()
    students = db.execute('''
        SELECT u.id, u.username, u.email, u.created_at, sp.education, sp.skills 
        FROM users u 
        LEFT JOIN student_profiles sp ON u.id = sp.user_id 
        WHERE u.role = "student" ORDER BY u.created_at DESC
    ''').fetchall()
    
    employers = db.execute('''
        SELECT u.id, u.username, u.email, u.created_at, e.company_name 
        FROM users u 
        LEFT JOIN employers e ON u.id = e.user_id 
        WHERE u.role = "employer" ORDER BY u.created_at DESC
    ''').fetchall()
    
    return render_template('admin_users.html', students=students, employers=employers)

@bp.route('/applications')
@login_required
def view_applications():
    db = get_db()
    applications = db.execute('''
        SELECT a.id, a.status, a.application_date, u.username as student_name, j.title as job_title, e.company_name 
        FROM applications a 
        JOIN users u ON a.student_id = u.id 
        JOIN jobs j ON a.job_id = j.id 
        JOIN employers e ON j.employer_id = e.user_id
        ORDER BY a.application_date DESC
    ''').fetchall()
    
    return render_template('admin_applications.html', applications=applications)
