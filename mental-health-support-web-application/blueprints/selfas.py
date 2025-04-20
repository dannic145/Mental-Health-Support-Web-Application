from flask import Flask, render_template, request, redirect, url_for, session
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Use a secure secret key

# Predefined questions for the self-assessment test
QUESTIONS = [
    "1. Have you been feeling sad, empty, or hopeless for more than two weeks?",
    "2. Have you been experiencing persistent and excessive worry about everyday things, such as work, finances, or relationships?",
    "3. Have you been having trouble sleeping or have you been sleeping too much?",
    "4. Have you been experiencing changes in appetite or weight?",
    "5. Have you been having trouble concentrating or making decisions?",
    "6. Have you been feeling anxious or on edge, and have you been avoiding certain situations or activities that trigger these feelings?",
    "7. Have you been experiencing flashbacks, nightmares, or intrusive thoughts related to a traumatic event?",
    "8. Have you been feeling fatigued or lacking energy, even after getting enough sleep?",
    "9. Have you been feeling irritable or easily annoyed, even over small things?",
    "10. Have you been feeling overwhelmed by your responsibilities, to the point where you feel unable to cope?"
]

@app.route('/self-assessment', methods=['GET', 'POST'])
def self_assessment():
    if request.method == 'POST':
        responses = request.form.getlist('response[]')
        feedback, solutions, issues = analyze_responses(responses)
        
        # Store feedback, solutions, and issues in the session
        session['feedback'] = feedback
        session['solutions'] = solutions
        session['issues'] = issues
        
        # Debugging: Print issues to the console to verify they are being stored
        print("Issues stored in session:", issues)
        
        return redirect(url_for('results'))
    
    return render_template('self_assessment.html', questions=QUESTIONS)

def analyze_responses(responses):
    score = 0
    issues = {
        "Depression": 0,
        "Anxiety": 0,
        "Sleep Issues": 0,
        "Appetite Changes": 0,
        "Concentration Issues": 0,
        "Trauma": 0,
        "Fatigue": 0,
        "Irritability": 0,
        "Overwhelm": 0
    }
    
    # Evaluate each response
    for i, response in enumerate(responses):
        response_value = int(response)  # Convert slider value to integer
        if response_value >= 4:  # High score (4 or 5)
            score += 2
            if i in [0, 1]:  # Depression-related questions
                issues["Depression"] += 1
            if i in [1, 5]:  # Anxiety-related questions
                issues["Anxiety"] += 1
            if i in [2, 7]:  # Sleep-related questions
                issues["Sleep Issues"] += 1
            if i == 3:  # Appetite-related questions
                issues["Appetite Changes"] += 1
            if i == 4:  # Concentration-related questions
                issues["Concentration Issues"] += 1
            if i == 6:  # Trauma-related questions
                issues["Trauma"] += 1
            if i == 7:  # Fatigue-related questions
                issues["Fatigue"] += 1
            if i == 8:  # Irritability-related questions
                issues["Irritability"] += 1
            if i == 9:  # Overwhelm-related questions
                issues["Overwhelm"] += 1
        elif response_value == 3:  # Moderate score (3)
            score += 1
        else:  # Low score (1 or 2)
            score += 0
    
    # Identify the most prominent issues
    prominent_issues = [issue for issue, count in issues.items() if count >= 2]
    
    # Provide feedback and solutions based on the score and issues
    if score >= 20:
        feedback = "You may be experiencing significant mental health challenges. It's important to seek professional help."
        solutions = [
            "Consider reaching out to a mental health professional.",
            "Practice mindfulness and relaxation techniques daily.",
            "Engage in regular physical activity to improve mood."
        ]
    elif score >= 10:
        feedback = "You may be experiencing some mental health challenges. It's a good idea to talk to someone you trust."
        solutions = [
            "Talk to a friend or family member about how you're feeling.",
            "Try journaling to express your thoughts and emotions.",
            "Establish a consistent sleep routine to improve rest."
        ]
    else:
        feedback = "Your mental health seems to be in good shape. Keep up the good work!"
        solutions = [
            "Continue practicing self-care and mindfulness.",
            "Stay connected with friends and loved ones.",
            "Engage in activities that bring you joy and relaxation."
        ]
    
    # Add specific feedback about issues
    if prominent_issues:
        feedback += f"\n\nYou may be facing challenges related to: {', '.join(prominent_issues)}."
    
    return feedback, solutions, prominent_issues

@app.route('/results')
def results():
    feedback = session.get('feedback', 'No feedback available.')
    solutions = session.get('solutions', [])
    issues = session.get('issues', [])  # Retrieve issues from the session
    
    # Debugging: Print issues to the console to verify they are being passed
    print("Issues being passed to template:", issues)
    
    return render_template('results.html', feedback=feedback, solutions=solutions, issues=issues)

if __name__ == '__main__':
    app.run(debug=True)