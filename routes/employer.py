from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import get_db
from utils import analyze_job_posting, role_required, generate_ai_job_description

bp = Blueprint('employer', __name__, url_prefix='/employer')

@bp.before_request
@role_required('employer')
def before_request():
    pass

@bp.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    page = request.args.get('page', 1, type=int)
    per_page = 5
    offset = (page - 1) * per_page
    
    total_jobs = db.execute("SELECT COUNT(*) FROM jobs WHERE employer_id = ?", (current_user.id,)).fetchone()[0]
    total_pages = (total_jobs + per_page - 1) // per_page

    my_jobs = db.execute('''
        SELECT j.*, (SELECT COUNT(*) FROM applications WHERE job_id = j.id) as applicant_count 
        FROM jobs j 
        WHERE j.employer_id = ? 
        ORDER BY j.created_at DESC
        LIMIT ? OFFSET ?
    ''', (current_user.id, per_page, offset)).fetchall()
    profile = db.execute("SELECT * FROM employers WHERE user_id = ?", (current_user.id,)).fetchone()
    
    return render_template('dashboard_employer.html', jobs=my_jobs, profile=profile, page=page, total_pages=total_pages)

@bp.route('/profile', methods=('GET', 'POST'))
@login_required
def profile():
    db = get_db()
    profile_data = db.execute("SELECT * FROM employers WHERE user_id = ?", (current_user.id,)).fetchone()
    
    if request.method == 'POST':
        name = request.form.get('company_name', '')
        desc = request.form.get('company_description', '')
        
        if profile_data:
            db.execute("UPDATE employers SET company_name = ?, company_description = ? WHERE user_id = ?",
                       (name, desc, current_user.id))
        else:
            db.execute("INSERT INTO employers (user_id, company_name, company_description) VALUES (?, ?, ?)",
                       (current_user.id, name, desc))
        db.commit()
        flash('Company profile updated.', 'success')
        return redirect(url_for('employer.dashboard'))
        
    return render_template('employer_profile.html', profile=profile_data)

@bp.route('/post_job', methods=('GET', 'POST'))
@login_required
def post_job():
    db = get_db()
    profile = db.execute("SELECT * FROM employers WHERE user_id = ?", (current_user.id,)).fetchone()
    if not profile:
        flash("You must complete your company profile before posting a job.", "warning")
        return redirect(url_for('employer.profile'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        stipend = request.form['stipend']
        location = request.form['location']
        
        # Analyze job with AI
        is_fake, reason = analyze_job_posting(title, description, stipend, location)
        if is_fake:
            flash(f"Job posting flagged as potential scam/fake by AI: {reason}", "error")
            return render_template('post_job.html', title=title, description=description, stipend=stipend, location=location)
        
        db.execute("INSERT INTO jobs (employer_id, title, description, stipend, location, status) VALUES (?, ?, ?, ?, ?, 'pending')",
                   (current_user.id, title, description, stipend, location))
        db.commit()
        flash('Job posted and awaiting admin verification.', 'success')
        return redirect(url_for('employer.dashboard'))
        
    return render_template('post_job.html')

@bp.route('/applicants/<int:job_id>')
@login_required
def applicants(job_id):
    db = get_db()
    # Verify employer owns job
    job = db.execute("SELECT * FROM jobs WHERE id = ? AND employer_id = ?", (job_id, current_user.id)).fetchone()
    if not job:
        flash("Unauthorized.", "error")
        return redirect(url_for('employer.dashboard'))
        
    applicants = db.execute("SELECT a.*, u.username, u.email, sp.education, sp.skills, sp.resume_path FROM applications a JOIN users u ON a.student_id = u.id LEFT JOIN student_profiles sp ON u.id = sp.user_id WHERE a.job_id = ? ORDER BY a.application_date DESC", (job_id,)).fetchall()
    
    return render_template('applicants.html', job=job, applicants=applicants)

@bp.route('/generate_jd', methods=['POST'])
@login_required
def generate_jd():
    data = request.get_json()
    if not data or 'requirements' not in data:
        return {"success": False, "error": "No requirements provided."}, 400
        
    requirements = data['requirements']
    jd_text = generate_ai_job_description(requirements)
    
    if jd_text.startswith("Error") or jd_text.startswith("System Error"):
        return {"success": False, "error": jd_text}, 500
        
    return {"success": True, "description": jd_text}

@bp.route('/delete_job/<int:job_id>', methods=['POST'])
@login_required
def delete_job(job_id):
    db = get_db()
    # Verify employer owns job
    job = db.execute("SELECT * FROM jobs WHERE id = ? AND employer_id = ?", (job_id, current_user.id)).fetchone()
    if not job:
        flash("Unauthorized or job not found.", "error")
        return redirect(url_for('employer.dashboard'))
        
    db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    db.commit()
    flash("Job posting successfully deleted.", "success")
    return redirect(url_for('employer.dashboard'))
