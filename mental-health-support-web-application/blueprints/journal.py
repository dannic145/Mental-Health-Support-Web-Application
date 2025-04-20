from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import datetime
from ..models import JournalEntry, db

# Create a Blueprint for journaling
journal_bp = Blueprint('journal', __name__, url_prefix='/journal')

# Journaling Routes
@journal_bp.route('/', methods=['GET', 'POST'])
def journal():
    if 'user_id' not in session:
        flash("You need to be logged in to access the journal.", 'error')
        return redirect(url_for('auth.login'))  # Redirect to login page
    
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
        return redirect(url_for('journal.journal'))
    
    # Fetch all journal entries for the user
    entries = JournalEntry.query.filter_by(user_id=session['user_id']).order_by(JournalEntry.date.desc()).all()
    return render_template('journal.html', entries=entries)

@journal_bp.route('/history')
def journal_history():
    if 'user_id' not in session:
        flash("You need to be logged in to view journal history.", 'error')
        return redirect(url_for('auth.login'))  # Redirect to login page
    
    # Fetch all journal entries for the user
    entries = JournalEntry.query.filter_by(user_id=session['user_id']).order_by(JournalEntry.date.desc()).all()
    return render_template('journal_history.html', entries=entries)