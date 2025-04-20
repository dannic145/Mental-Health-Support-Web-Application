from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
import requests
from sqlalchemy import func
import toml
import re
import os
import sqlite3
import time
import random
from threading import Lock
from functools import wraps
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db, limiter, security
from blueprints.peacepal import peacepal_app
from blueprints.mood import mood_bp, goals_bp  
from blueprints.coping import generate_coping_mechanisms
from models import User, JournalEntry, MoodEntry, Goal


def create_app():
    # Create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.secret_key = os.urandom(24)
    # Configure instance path
    instance_path = os.path.join(app.root_path, 'instance')
    os.makedirs(instance_path, exist_ok=True)
    
    # Application Configuration
    app.config.update({
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{os.path.join(instance_path, "users.db")}',
        'SQLALCHEMY_BINDS': {
            'security': f'sqlite:///{os.path.join(instance_path, "security.db")}',
            'rate_limit': f'sqlite:///{os.path.join(instance_path, "rate_limit.db")}'
        },
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'RATE_LIMITING_ENABLED': True,
        'MAX_FAILED_ATTEMPTS': 3,
        'BLOCK_DURATION': 60,
        'CAPTCHA_ENABLED': True,
        'PERMANENT_SESSION_LIFETIME': 3600,
        'SESSION_REFRESH_EACH_REQUEST': True
    })

    # Initialize extensions
    db.init_app(app)
    limiter.init_app(app)
    security.init_app(app)
    
    # Register blueprints
    app.register_blueprint(peacepal_app, url_prefix='/peacepal')
    app.register_blueprint(mood_bp, url_prefix='/mood')
    app.register_blueprint(goals_bp, url_prefix='/goals')

    # Create database tables
    with app.app_context():
        # Create main database tables
        db.create_all()
        
        # Initialize security system databases
        security._init_db()
        limiter._init_db()

    # Password strength checker
    def is_password_strong(password):
    # Common passwords check
        common_passwords = [
            'password', '123456', '12345678', 'qwerty', 'abc123',
            'letmein', 'admin', 'welcome', 'sunshine', 'football'
        ]
        if password.lower() in common_passwords:
            return False, "Password is too common and easily guessable"

        # Length check
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"

        # Character type check
        checks = {
            'uppercase': re.search(r'[A-Z]', password),
            'lowercase': re.search(r'[a-z]', password),
            'digit': re.search(r'\d', password),
            'special': re.search(r'[^A-Za-z0-9]', password)
        }
        met = sum(1 for check in checks.values() if check)
        if met < 3:
            return False, "Password must contain at least 3 of: uppercase, lowercase, numbers, special characters"

        # Pattern checks
        if re.search(r'(.)\1{3,}', password):  # 4+ repeated characters
            return False, "Password contains too many repeated characters"
        
        if re.search(r'(0123|1234|2345|3456|4567|5678|6789|7890|abcd|bcde|cdef|defg)', password.lower()):
            return False, "Password contains sequential patterns that are easy to guess"

        return True, "Password strength is good"

    # Security checks
    @app.before_request
    def security_checks():
        session.permanent = True
        if security.check_blocked():
            return render_template('security_blocked.html', 
                                remaining_time=app.config['BLOCK_DURATION']), 403
        if 'csrf_token' not in session:
            session['csrf_token'] = os.urandom(16).hex()

    # Application Routes
    @app.route('/')
    def pre_entry():
        return render_template('pre_entry.html')

    @app.route('/unblock')
    def unblock_ip():
        if app.debug:
            ip = request.remote_addr
            with sqlite3.connect(app.config['SQLALCHEMY_BINDS']['security'].replace('sqlite:///', '')) as conn:
                conn.execute('DELETE FROM blocked_ips WHERE ip = ?', (ip,))
                conn.execute('DELETE FROM failed_attempts WHERE ip = ?', (ip,))
            session.pop('captcha_passed', None)
            flash("IP unblocked for testing", 'success')
            return redirect(url_for('home'))
        return "Not allowed", 403

    @app.route('/captcha', methods=['GET', 'POST'])
    @limiter.limit('5 per hour')
    def captcha_challenge():
        if request.method == 'POST':
            if session.get('csrf_token') != request.form.get('csrf_token'):
                flash("Invalid form submission", 'error')
                return redirect(url_for('captcha_challenge'))
            
            if str(session.get('captcha_answer', '')).strip() != request.form.get('answer', '').strip():
                flash("Incorrect answer, please try again", 'error')
                return redirect(url_for('captcha_challenge'))
            
            security.reset_failed_attempts(request.remote_addr)
            session['captcha_passed'] = True
            return redirect(request.args.get('next', url_for('home')))
        
        num1 = random.randint(1, 9)
        num2 = random.randint(1, 9)
        session['captcha_answer'] = num1 + num2
        return render_template('security_captcha.html', 
                            problem=f"{num1} + {num2}",
                            csrf_token=session['csrf_token'])

    @app.route('/login', methods=['GET', 'POST'])
    @limiter.limit('5 per hour')
    @security.requires_captcha
    def login():
        if request.method == 'POST':
            if session.get('csrf_token') != request.form.get('csrf_token'):
                flash("Invalid form submission", 'error')
                return redirect(url_for('login'))
            
            username = request.form['username']
            password = request.form['password']
            user = User.query.filter_by(username=username).first()

            if user and check_password_hash(user.password, password):
                session['user_id'] = user.id
                session['username'] = user.username
                session.pop('captcha_passed', None)
                flash("Login successful!", 'success')
                return redirect(url_for('dashboard'))
            else:
                security.track_failed_attempt(request.remote_addr)
                flash("Invalid username or password", 'error')
        return render_template('login.html', csrf_token=session['csrf_token'])

    @app.route('/signup', methods=['GET', 'POST'])
    @limiter.limit('3 per hour')
    @security.requires_captcha
    def signup():
        if request.method == 'POST':
            if session.get('csrf_token') != request.form.get('csrf_token'):
                flash("Invalid form submission", 'error')
                return redirect(url_for('signup'))
            
            name = request.form['name']
            email = request.form['email']
            username = request.form['username']
            password = request.form['password']

            # Password strength check
            is_strong, message = is_password_strong(password)
            if not is_strong:
                flash(f"Password too weak: {message}", 'error')
                return render_template('signup.html', csrf_token=session['csrf_token'])

            if User.query.filter_by(username=username).first():
                flash("Username already exists!", 'error')
                return render_template('signup.html', csrf_token=session['csrf_token'])
            
            if User.query.filter_by(email=email).first():
                flash("Email already registered!", 'error')
                return render_template('signup.html', csrf_token=session['csrf_token'])

            try:
                hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
                new_user = User(
                    name=name,
                    email=email,
                    username=username,
                    password=hashed_password
                )
                db.session.add(new_user)
                db.session.commit()
                flash("Signup successful! Please log in.", 'success')
                return redirect(url_for('login'))
            except Exception as e:
                flash(f"Error creating account: {str(e)}", 'error')
        
        return render_template('signup.html', csrf_token=session['csrf_token'])

    @app.route('/goodbye')
    def goodbye():
        return render_template('goodbye.html')

    @app.route('/home')
    def home():
        return render_template('home.html')

    @app.route('/dashboard')
    def dashboard():
        if 'user_id' not in session:
            flash("You need to be logged in to view the dashboard", 'error')
            return redirect(url_for('login'))
        
        # Get mood data
        mood_entries = MoodEntry.query.filter_by(user_id=session['user_id'])\
                        .order_by(MoodEntry.timestamp.desc())\
                        .limit(7)\
                        .all()
        
        # Get goals
        goals = Goal.query.filter_by(user_id=session['user_id'])\
                .order_by(Goal.created_at.desc())\
                .all()

        # Prepare chart data
        mood_dates = [entry.timestamp.strftime('%Y-%m-%d') for entry in mood_entries]
        mood_levels = [entry.mood_level for entry in mood_entries]

        return render_template('dashboard.html',
                            username=session['username'],
                            mood_dates=mood_dates,
                            mood_levels=mood_levels,
                            goals=goals)

    @app.route('/aboutus')
    def aboutus():
        return render_template('aboutus.html')

    @app.route('/logout')
    def logout():
        session.pop('user_id', None)
        session.pop('username', None)
        flash("You have been logged out.", 'success')
        return redirect(url_for('home'))

    @app.route('/breathing-exercise')
    def breathing_exercise():
        return render_template('breathing_exercise.html')

    @app.route('/meditation-technique')
    def meditation_technique():
        return render_template('meditation_technique.html')

    @app.route('/journal', methods=['GET', 'POST'])
    def journal():
        if 'user_id' not in session:
            flash("You need to be logged in to access the journal.", 'error')
            return redirect(url_for('login'))
        
        if request.method == 'POST':
            entry = request.form['entry']
            activity = request.form['activity']
            date = datetime.now().strftime("%Y-%m-%d")
            
            new_entry = JournalEntry(
                user_id=session['user_id'],
                date=date,
                entry=entry,
                activity=activity
            )
            
            db.session.add(new_entry)
            db.session.commit()
            flash("Journal entry saved successfully!", 'success')
            return redirect(url_for('journal'))
        
        entries = JournalEntry.query.filter_by(user_id=session['user_id']).order_by(JournalEntry.date.desc()).all()
        return render_template('journal.html', entries=entries)

    @app.route('/journal/history')
    def journal_history():
        if 'user_id' not in session:
            flash("You need to be logged in to view journal history.", 'error')
            return redirect(url_for('login'))
        
        entries = JournalEntry.query.filter_by(user_id=session['user_id']).order_by(JournalEntry.date.desc()).all()
        return render_template('journal_history.html', entries=entries)

    @app.route('/self-assessment', methods=['GET', 'POST'])
    def self_assessment():
        if request.method == 'POST':
            responses = request.form.getlist('response[]')
            feedback, solutions = analyze_responses(responses)
            session['feedback'] = feedback
            session['solutions'] = solutions
            return redirect(url_for('results'))

        questions = [
            "Have you been feeling sad or hopeless?",
            "Have you experienced loss of interest in activities?",
            "Have you had changes in appetite or weight?",
            "Have you had sleep disturbances?",
            "Do you experience fatigue or energy loss?",
            "Do you have feelings of worthlessness?",
            "Do you have difficulty concentrating?",
            "Do you experience physical restlessness?",
            "Have you had thoughts of self-harm?",
            "Do you experience anxiety attacks?"
        ]
        return render_template('self_assessment.html', questions=questions)

    def analyze_responses(responses):
        try:
            api_key = toml.load('key.toml')['api']['key']
            prompt = f"""Analyze these mental health assessment responses:
            {responses}
            
            Provide:
            1. Potential mental health considerations (max 4)
            2. Severity assessment (mild/moderate/severe)
            3. 5-7 personalized recommendations
            4. Professional help guidance
            
            Format clearly with section headings without markdown syntax."""

            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": "You are a mental health counselor."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 500
            }

            response = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
                json=payload
            )

            if response.status_code == 200:
                content = response.json()['choices'][0]['message']['content']
                sections = content.split('\n\n')
                diagnosis = sections[0] if len(sections) > 0 else "No diagnosis available"
                solutions = sections[1].split('\n') if len(sections) > 1 else ["Recommendations unavailable"]
                return diagnosis, solutions
            return ("API service unavailable", ["Please try again later"])

        except Exception as e:
            print(f"Error: {e}")
            return ("Diagnosis unavailable", ["Consult a mental health professional"])

    @app.route('/results')
    def results():
        diagnosis = session.get('feedback', 'No diagnosis available')
        solutions = session.get('solutions', [])
        return render_template('results.html', 
                            diagnosis=diagnosis,
                            solutions=solutions)

    @app.route('/coping', methods=['GET', 'POST'])
    def coping():
        if 'user_id' not in session:
            flash("You need to be logged in to access coping mechanisms.", 'error')
            return redirect(url_for('login'))
        
        if request.method == 'POST':
            user_input = request.form['user_input']
            coping_mechanisms = generate_coping_mechanisms(user_input)
            return render_template('coping_results.html', coping_mechanisms=coping_mechanisms)
        
        return render_template('coping.html')

    @app.route('/referrals', methods=['GET', 'POST'])
    def referrals():
        if 'user_id' not in session:
            flash("You need to be logged in to access referrals.", 'error')
            return redirect(url_for('login'))
        
        if request.method == 'POST':
            country = request.form['country']
            state = request.form['state']
            city = request.form['city']
            referrals = generate_referrals(country, state, city)
            return render_template('referrals_results.html', referrals=referrals)
        
        return render_template('referrals.html')

    def generate_referrals(country, state, city):
        api_key = toml.load('key.toml')['api']['key']
        messages = [
            {"role": "system", "content": """You are a mental health assistant. Provide a list of licensed mental health specialists in the user's area using this format:
    Name: [Full Name]
    Qualifications: [Degrees/Certifications]
    Specialization: [Areas of Expertise]
    Contact: [Phone/Email]
    Location: [Clinic Address]
    ---"""},
            {"role": "user", "content": f"I am located in {city}, {state}, {country}. List 5 licensed mental health specialists near me."}
        ]
        
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": messages,
            "max_tokens": 500,  # Increased for more detailed responses
            "temperature": 0.7
        }
        
        try:
            response = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'},
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                content = response.json().get('choices', [{}])[0].get('message', {}).get('content', '')
                return content.strip()
            return "Failed to retrieve specialists. Please try again later."
        
        except Exception as e:
            return f"Error connecting to service: {str(e)}"

    @app.route('/progress')
    def progress():
        if 'user_id' not in session:
            flash("Please login to view progress", "error")
            return redirect(url_for('login'))
        
        user_id = session['user_id']
        
        # Get mood data
        moods = MoodEntry.query.filter_by(user_id=user_id).order_by(MoodEntry.timestamp).all()
        mood_dates = [m.timestamp.strftime('%Y-%m-%d') for m in moods]
        mood_levels = [m.mood_level for m in moods]
        
        # Get goals
        goals = Goal.query.filter_by(user_id=user_id).all()
        
        # Get journal stats
        journal_count = JournalEntry.query.filter_by(user_id=user_id).count()
        most_active_day = db.session.query(
            JournalEntry.date,
            func.count(JournalEntry.id).label('count')

            
        ).filter_by(user_id=user_id).group_by(JournalEntry.date).order_by(func.count(JournalEntry.id).desc()).first()
        
        most_active_day = most_active_day[0] if most_active_day else "N/A"
        
        # Simple theme analysis (you can enhance this)
        entries = JournalEntry.query.filter_by(user_id=user_id).limit(10).all()
        common_themes = list(set([entry.entry.split()[0] for entry in entries if entry.entry]))[:5]
        
        return render_template('progress.html',
                            mood_dates=mood_dates,
                            mood_levels=mood_levels,
                            goals=goals,
                            journal_count=journal_count,
                            most_active_day=most_active_day,
                            common_themes=common_themes)
    
    @app.route('/terms')
    def terms():
        return render_template('terms.html', current_date=datetime.now())

    @app.route('/privacy')
    def privacy():
        return render_template('privacy.html', current_date=datetime.now())

    @app.errorhandler(429)
    def ratelimit_handler(e):
        return render_template('rate_limit.html'), 429

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)