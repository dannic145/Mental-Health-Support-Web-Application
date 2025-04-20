from flask import Flask
from .models import db
from .blueprints.journal import journal_bp

def create_app():
    app = Flask(__name__)
    app.secret_key = 'your_secret_key'
    
    # Configure SQLite database
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///journal.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize the database
    db.init_app(app)
    
    # Register Blueprints
    app.register_blueprint(journal_bp)
    