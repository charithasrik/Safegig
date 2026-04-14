import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from functools import wraps
from functools import wraps
from flask import abort, current_app, redirect, url_for, flash
from flask_login import current_user
from itsdangerous import URLSafeTimedSerializer

load_dotenv()

# Configure Gemini API
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

generation_config = {
  "temperature": 0.1,
  "top_p": 0.95,
  "top_k": 40,
  "max_output_tokens": 1024,
  "response_mime_type": "application/json",
}

def role_required(*roles):
    """Decorator to restrict access by user role."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return current_app.login_manager.unauthorized()
            if current_user.role not in roles:
                flash('Unauthorized access.', 'error')
                return redirect(url_for('public.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator



def analyze_job_posting(title, description, stipend, location):
    """
    Analyzes a job posting using Gemini to determine if it is fake or a scam.
    Returns a tuple: (is_fake (bool), reason (str))
    """
    if not api_key:
        print("Warning: GEMINI_API_KEY is not set.")
        return False, ""

    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config=generation_config,
            system_instruction=(
                "You are an expert fraud detection AI for a student job board called SafeGig. "
                "Analyze the provided job posting for signs of it being a scam, fake job, MLM (Multi-Level Marketing), "
                "or generally exploiting students. Look out for: "
                "1. Requests for upfront payment or fees. "
                "2. Promising unrealistically high pay for little work or no experience. "
                "3. Vague job descriptions lacking specific duties. "
                "4. Asking candidates to urgently contact via unverified personal numbers/WhatsApp/Telegram. "
                "5. Common phishing links or suspicious email addresses. "
                "Rate 'is_fake' as true if you are confident it is a scam or unsafe for students, and provide a clear, concise 'reason' explaining why. "
                "If it appears to be a legitimate job, 'is_fake' should be false and 'reason' should be empty or 'Looks legitimate'. "
                "Output STRICTLY in JSON format: {\"is_fake\": boolean, \"reason\": \"string\"}."
            )
        )
        
        prompt = f"Job Title: {title}\nJob Description: {description}\nStipend/Pay: {stipend}\nLocation: {location}"
        response = model.generate_content(prompt)
        
        result = json.loads(response.text)
        return result.get('is_fake', False), result.get('reason', '')
        
    except Exception as e:
        print(f"Error in Gemini API: {e}")
        # In case of an API error, default to False to avoid blocking legitimate users, 
        # or flag it. For now, we will return False.
        return False, f"Error analyzing job: {str(e)}"

def generate_ai_job_description(requirements):
    """Generates a professional job description from simple requirements using Gemini."""
    if not api_key:
        return "Error: Gemini API key is not configured."
        
    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            generation_config={"temperature": 0.5, "max_output_tokens": 4096},
            system_instruction=(
                "You are an expert HR recruiter writing a job posting. Create a professional, engaging, "
                "and clearly structured job description based on the provided requirements or prompt. "
                "Format carefully with clear paragraphs and bullet points. Include standard elements like "
                "'About the Role', 'Responsibilities', and 'Requirements' if they fit. "
                "Do NOT use markdown bolding or asterisks (like **) in the text "
                "- rely on capital letters for headers and standard dash bullet points to keep it clean for simple text areas."
            )
        )
        response = model.generate_content(f"Raw requirements:\n{requirements}")
        # Strip simple markdown traces that might break textarea pure-text look
        clean_text = response.text.replace('**', '').replace('__', '')
        return clean_text.strip()
    except Exception as e:
        print(f"Error in Gemini JD Generator API: {e}")
        return "System Error generating job description. Please write it manually."

import PyPDF2
from docx import Document
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def extract_text_from_resume(filepath):
    """Extract text from a .pdf, .doc, or .docx file."""
    if not os.path.exists(filepath):
        return ""
        
    ext = filepath.rsplit('.', 1)[1].lower() if '.' in filepath else ''
    text = ""
    
    try:
        if ext == 'pdf':
            with open(filepath, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + " "
        elif ext in ['docx', 'doc']:
            doc = Document(filepath)
            for para in doc.paragraphs:
                text += para.text + " "
    except Exception as e:
        print(f"Error extracting text from {filepath}: {e}")
        
    return text.strip()

def get_job_recommendations(resume_text, jobs):
    """
    Given a resume string and a list of job dicts (raw sqlite3 Row objects or dicts),
    Returns jobs with an added 'match_score' key, sorted by highest matching.
    """
    if not resume_text or not jobs:
        # If no resume text, return regular list but as dicts and no match scores
        return [dict(j) for j in jobs]
        
    # Create corpus: [resume_text, job_desc_1, job_desc_2, ...]
    job_texts = [f"{job['title']} {job['description']}" for job in jobs]
    corpus = [resume_text] + job_texts
    
    vectorizer = TfidfVectorizer(stop_words='english')
    try:
        tfidf_matrix = vectorizer.fit_transform(corpus)
    except ValueError:
        return [dict(j) for j in jobs]
        
    # Calculate cosine similarity between resume (index 0) and all jobs
    similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
    
    recommended_jobs = []
    for i, job in enumerate(jobs):
        job_dict = dict(job)
        # Cosine similarity between small documents (like resumes and job postings)
        # is often very low (0.05 - 0.20 range). We can apply a multiplier or scale it 
        # so it makes more intuitive sense to a user as a "Match %".
        raw_score = similarities[i]
        
        # Scaling trick: multiply by 4 to boost the percentage numbers, cap at 99%.
        adjusted_score = min(raw_score * 4.0, 0.99)
        
        job_dict['match_score_raw'] = adjusted_score
        job_dict['match_score'] = f"{int(adjusted_score * 100)}%"
        recommended_jobs.append(job_dict)
        
    # Sort by match score descending
    recommended_jobs.sort(key=lambda x: x['match_score_raw'], reverse=True)
    
    return recommended_jobs
