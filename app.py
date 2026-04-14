import os
from dotenv import load_dotenv

load_dotenv()

from flask import Flask
from flask_login import LoginManager

# Local imports moved to top level to resolve IDE import errors
from models import close_db, init_db, User
from routes import auth, public, student, employer, admin
from flask_wtf.csrf import CSRFProtect

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    
    app.config.from_mapping(
        SECRET_KEY='dev-secret-key-change-in-production',
        POSTGRES_URL=os.environ.get('POSTGRES_URL', 'postgresql://localhost/safegig'),
        UPLOAD_FOLDER=os.path.join(app.root_path, 'uploads'),
        MAX_CONTENT_LENGTH=16 * 1024 * 1024, # Limit upload size to 16MB
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax'
    )
    
    # Initialize CSRF Protection
    csrf = CSRFProtect()
    csrf.init_app(app)
    
    # Ensure instance and upload folders exist
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Setup Database teardown and commands
    app.teardown_appcontext(close_db)
    
    @app.cli.command('init-db')
    def init_db_command():
        """Clear the existing data and create new tables."""
        init_db()
        print('Initialized the database.')
        
    # Setup Flask-Login
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'warning'
    login_manager.init_app(app)
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.get(user_id)
        
    # Register Blueprints
    app.register_blueprint(auth.bp)
    app.register_blueprint(public.bp)
    app.register_blueprint(student.bp)
    app.register_blueprint(employer.bp)
    app.register_blueprint(admin.bp)
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
