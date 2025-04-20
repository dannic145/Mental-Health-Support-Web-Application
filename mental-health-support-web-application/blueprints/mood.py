from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from datetime import datetime, timedelta
from extensions import db
from models import MoodEntry, Goal
import os
import toml
import requests

# Create Blueprints
mood_bp = Blueprint('mood_bp', __name__)
goals_bp = Blueprint('goals_bp', __name__)

# Load Groq API configuration
config_path = os.path.join(os.path.dirname(__file__), "key.toml")
config = toml.load(config_path)
api_key = config['api']['key']

def get_authenticated_user():
    """Get authenticated user from session"""
    return session.get('user_id')

def generate_ai_response(prompt, context=""):
    """Generate AI-powered mental health response using Groq API"""
    messages = [
        {
            "role": "system",
            "content": f"ACT AS MENTAL COACH. PROVIDE ACTIONABLE ADVICE. NO MARKDOWN. KEEP IT SHORT. DON'T ASK ANY QUESTIONS TO USER. CONTEXT: {context}"
        },
        {
            "role": "user", 
            "content": prompt
        }
    ]
    
    try:
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization': f'Bearer {api_key}'},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "max_tokens": 150,
                "temperature": 0.7
            },
            timeout=10
        )
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        print(f"AI API Error: {str(e)}")
        return "System optimizing. Focus on immediate action steps."

# Mood Routes
@mood_bp.route('/', methods=['GET'])
def mood_tracker():
    user_id = get_authenticated_user()
    if not user_id:
        return redirect(url_for('login'))
    
    moods = MoodEntry.query.filter_by(user_id=user_id).order_by(MoodEntry.timestamp.desc()).limit(14).all()
    return render_template('mood.html',
                         mood_dates=[m.timestamp.strftime('%Y-%m-%d') for m in moods],
                         mood_levels=[m.mood_level for m in moods],
                         analysis=session.pop('analysis', None))

@mood_bp.route('/log', methods=['POST'])
def log_mood():
    user_id = get_authenticated_user()
    if not user_id:
        flash("Authentication required", "error")
        return redirect(url_for('login'))

    try:
        new_entry = MoodEntry(
            user_id=user_id,
            mood_level=int(request.form.get('mood_level', 5)),
            notes=request.form.get('notes', '').strip(),
            timestamp=datetime.utcnow()
        )
        
        db.session.add(new_entry)
        db.session.commit()
        flash("Mood logged successfully!", "success")
        
        session['analysis'] = generate_ai_response(
            f"New mood logged: {new_entry.mood_level}/10. Notes: {new_entry.notes}",
            "Mood pattern analysis"
        )
        
    except ValueError:
        flash("Invalid mood level format", "error")
    except Exception as e:
        print(f"Error logging mood: {str(e)}")
        flash("Failed to log mood entry", "error")
    
    return redirect(url_for('mood_bp.mood_tracker'))

# Goals Routes
@goals_bp.route('/', methods=['GET', 'POST'])
def manage_goals():
    user_id = get_authenticated_user()
    if not user_id:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            goal = Goal(
                user_id=user_id,
                title=request.form['title'],
                target_date=datetime.strptime(request.form['target_date'], '%Y-%m-%d'),
                progress=0
            )
            db.session.add(goal)
            db.session.commit()
            flash('Goal created successfully!', 'success')
        except Exception as e:
            print(f"Goal creation error: {str(e)}")
            flash('Failed to create goal', 'error')

    goals = Goal.query.filter_by(user_id=user_id).all()
    return render_template('goals.html', goals=goals)

@goals_bp.route('/update_progress/<int:goal_id>', methods=['POST'])
def update_progress(goal_id):
    user_id = get_authenticated_user()
    if not user_id:
        return redirect(url_for('login'))

    goal = Goal.query.filter_by(id=goal_id, user_id=user_id).first()
    if not goal:
        flash('Goal not found', 'error')
        return redirect(url_for('goals_bp.manage_goals'))

    try:
        goal.progress = int(request.form['progress'])
        db.session.commit()
        flash('Progress updated!', 'success')
    except ValueError:
        flash('Invalid progress value', 'error')
    
    return redirect(url_for('goals_bp.manage_goals'))

# AI Integration Routes
@mood_bp.route('/analyze', methods=['GET'])
def analyze_mood():
    user_id = get_authenticated_user()
    if not user_id:
        return redirect(url_for('login'))
    
    moods = MoodEntry.query.filter(
        MoodEntry.user_id == user_id,
        MoodEntry.timestamp >= datetime.now() - timedelta(days=7)
    ).all()
    
    analysis = generate_ai_response(
        f"Analyze these mood scores: {[m.mood_level for m in moods]}",
        "Mood pattern analysis"
    )
    
    return render_template('mood.html',
                         mood_dates=[m.timestamp.strftime('%Y-%m-%d') for m in moods],
                         mood_levels=[m.mood_level for m in moods],
                         analysis=analysis)

@goals_bp.route('/goal/<int:goal_id>/advice', methods=['GET'])
def goal_advice(goal_id):
    user_id = get_authenticated_user()
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    goal = Goal.query.filter_by(id=goal_id, user_id=user_id).first()
    return jsonify({"advice": generate_ai_response(
        f"Provide 5 tactical steps to achieve: {goal.title}",
        "Goal achievement strategies"
    )}) if goal else (jsonify({"error": "Goal not found"}), 404)