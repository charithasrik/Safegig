import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import get_db
from utils import extract_text_from_resume, get_job_recommendations, role_required

bp = Blueprint('student', __name__, url_prefix='/student')

@bp.before_request
@role_required('student')
def before_request():
    pass

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'pdf', 'doc', 'docx'}



@bp.route('/dashboard')
@login_required
def dashboard():
    page = request.args.get('page', 1, type=int)
    per_page = 5
    offset = (page - 1) * per_page
    
    db = get_db()
    
    total_jobs = db.execute("SELECT COUNT(*) FROM jobs WHERE status = 'verified'").fetchone()[0]
    total_pages = (total_jobs + per_page - 1) // per_page
    
    # Verified jobs
    verified_jobs = db.execute("SELECT j.*, e.company_name FROM jobs j JOIN employers e ON j.employer_id = e.user_id WHERE j.status = 'verified' ORDER BY j.created_at DESC LIMIT ? OFFSET ?", (per_page, offset)).fetchall()
    
    # Applied job IDs mapping
    applied_job_ids = [app['job_id'] for app in db.execute("SELECT job_id FROM applications WHERE student_id = ?", (current_user.id,)).fetchall()]
    
    # Saved jobs
    saved_jobs = db.execute("SELECT j.*, e.company_name FROM saved_jobs s JOIN jobs j ON s.job_id = j.id JOIN employers e ON j.employer_id = e.user_id WHERE s.student_id = ? ORDER BY s.created_at DESC", (current_user.id,)).fetchall()
    
    # Profile check
    profile = db.execute("SELECT * FROM student_profiles WHERE user_id = ?", (current_user.id,)).fetchone()
    
    # AI Recommendations
    recommended_jobs = []
    if profile and profile['resume_text'] and verified_jobs:
        recommended_jobs = get_job_recommendations(profile['resume_text'], verified_jobs)
        # Only take the top 3 recommendations that have > 0% match (or just top 3)
        recommended_jobs = [j for j in recommended_jobs if j['match_score_raw'] > 0.05][:3]
    
    return render_template('dashboard_student.html', jobs=verified_jobs, applied_job_ids=applied_job_ids, saved_jobs=saved_jobs, profile=profile, recommended_jobs=recommended_jobs, total_pages=total_pages, page=page)

@bp.route('/applications')
@login_required
def my_applications():
    db = get_db()
    applications = db.execute("SELECT j.title, j.id as job_id, j.employer_id, e.company_name, a.application_date, a.status, a.availability, a.start_date, a.previous_experience FROM applications a JOIN jobs j ON a.job_id = j.id JOIN employers e ON j.employer_id = e.user_id WHERE a.student_id = ? ORDER BY a.application_date DESC", (current_user.id,)).fetchall()
    return render_template('my_applications.html', applications=applications)

@bp.route('/saved')
@login_required
def saved_jobs():
    db = get_db()
    saved_jobs = db.execute("SELECT j.*, e.company_name FROM saved_jobs s JOIN jobs j ON s.job_id = j.id JOIN employers e ON j.employer_id = e.user_id WHERE s.student_id = ? ORDER BY s.created_at DESC", (current_user.id,)).fetchall()
    return render_template('saved_jobs.html', saved_jobs=saved_jobs)

@bp.route('/profile', methods=('GET', 'POST'))
@login_required
def profile():
    db = get_db()
    profile_data = db.execute("SELECT * FROM student_profiles WHERE user_id = ?", (current_user.id,)).fetchone()
    
    if request.method == 'POST':
        education = request.form.get('education', '')
        skills = request.form.get('skills', '')
        
        # Handle resume upload
        resume_path = profile_data['resume_path'] if profile_data else None
        resume_text = profile_data['resume_text'] if profile_data else None
        
        if 'resume' in request.files:
            file = request.files['resume']
            if file and file.filename != '':
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    if not filename:
                        filename = "resume.pdf"
                    filename = f"user_{current_user.id}_{filename}"
                    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    resume_path = filename
                    
                    # Extract text from the newly uploaded resume to power AI recommendations
                    resume_text = extract_text_from_resume(file_path)
                else:
                    flash('Invalid file type for resume. Please upload a PDF or DOC/DOCX file.', 'error')
                    return redirect(url_for('student.profile'))
        
        if profile_data:
            db.execute("UPDATE student_profiles SET education = ?, skills = ?, resume_path = ?, resume_text = ? WHERE user_id = ?",
                       (education, skills, resume_path, resume_text, current_user.id))
        else:
            db.execute("INSERT INTO student_profiles (user_id, education, skills, resume_path, resume_text) VALUES (?, ?, ?, ?, ?)",
                       (current_user.id, education, skills, resume_path, resume_text))
        
        db.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('student.dashboard'))
        
    return render_template('profile.html', profile=profile_data)

@bp.route('/job/<int:job_id>')
@login_required
def job_detail(job_id):
    db = get_db()
    job = db.execute("SELECT j.*, e.company_name, e.company_description FROM jobs j JOIN employers e ON j.employer_id = e.user_id WHERE j.id = ?", (job_id,)).fetchone()
    if not job:
        flash("Job not found.", "error")
        return redirect(url_for('student.dashboard'))
        
    application = db.execute("SELECT * FROM applications WHERE student_id = ? AND job_id = ?", (current_user.id, job_id)).fetchone()
    is_saved = db.execute("SELECT * FROM saved_jobs WHERE student_id = ? AND job_id = ?", (current_user.id, job_id)).fetchone() is not None
    
    feedbacks = db.execute("SELECT f.*, u.username as student_name FROM feedbacks f JOIN users u ON f.student_id = u.id WHERE f.job_id = ? ORDER BY f.created_at DESC", (job_id,)).fetchall()
    
    return render_template('job_detail.html', job=job, has_applied=(application is not None), is_saved=is_saved, feedbacks=feedbacks)

@bp.route('/apply/<int:job_id>', methods=['POST'])
@login_required
def apply_job(job_id):
    db = get_db()
    # Check if profile holds a resume first
    profile = db.execute("SELECT * FROM student_profiles WHERE user_id = ?", (current_user.id,)).fetchone()
    if not profile or not profile['resume_path']:
        flash("You must complete your profile and upload a resume before applying.", "error")
        return redirect(url_for('student.profile'))
        
    availability = request.form.get('availability', '')
    start_date = request.form.get('start_date', '')
    previous_experience = request.form.get('previous_experience', '')
        
    try:
        db.execute("INSERT INTO applications (student_id, job_id, availability, start_date, previous_experience) VALUES (?, ?, ?, ?, ?)", (current_user.id, job_id, availability, start_date, previous_experience))
        db.commit()
        flash("Successfully applied!", "success")
    except Exception:
        flash("You already applied.", "warning")
        
    return redirect(url_for('student.job_detail', job_id=job_id))

@bp.route('/save/<int:job_id>', methods=['POST'])
@login_required
def save_job(job_id):
    db = get_db()
    db.execute("INSERT INTO saved_jobs (student_id, job_id) VALUES (?, ?) ON CONFLICT DO NOTHING", (current_user.id, job_id))
    db.commit()
    flash("Job saved to your dashboard.", "success")
    return redirect(url_for('student.job_detail', job_id=job_id))

@bp.route('/feedback/<int:job_id>', methods=['POST'])
@login_required
def submit_feedback(job_id):
    db = get_db()
    rating = request.form['rating']
    comment = request.form['comment']
    
    db.execute("INSERT INTO feedbacks (job_id, student_id, rating, comment) VALUES (?, ?, ?, ?)",
               (job_id, current_user.id, rating, comment))
    db.commit()
    flash('Feedback submitted successfully.', 'success')
    return redirect(url_for('student.job_detail', job_id=job_id))
