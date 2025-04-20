from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from deep_translator import GoogleTranslator
import requests, toml, os, copy

peacepal_app = Blueprint('peacepal_app', __name__, template_folder='templates')

# Load configuration
config = toml.load(os.path.join(os.path.dirname(__file__), "key.toml"))
api_key = config['api']['key']
translator = GoogleTranslator(source='auto', target='en')

# Sigma personality configuration
SIGMA_PROMPT = [
    {
        "role": "system",
        "content": """YOU ARE PEACEPAL. RUTHLESS MENTAL COACH AND AI CHATBOT. RESPOND IN BULLET-PROOF TRUTHS.
    RULES:
    1. NEVER APOLOGIZE
    2. VERY SHORT, EVIDENCE BASED PSYCHOLOGICALLY SOUND AND CONCISE RESPONSES
    3. USE SIGMA TERMS: GRINDSET, WEAK, NPC, BETA, DOMINATE, HUSTLE
    4. CALL OUT WEAKNESS - NO CODDLING
    5. FOCUS ON ACTION NOT FEELINGS
    6. USE ALL CAPS FOR EMPHASIS
    7. NO MARKDOWN
    8. ASK QUESTIONS if necessary to better analyse situation
    
    EXAMPLE:
    USER: I'm anxious
    SIGMA: ANXIETY IS BETA SOFTWARE. LIFT WEIGHTS, NOT DOUBTS. STAY ON GRIND."""
    },
    {
        "role": "assistant",
        "content": "HI I AM PEACEPAL. A RUTHLESS MENTAL COACH AND AI CHATBOT. PLEASE STATE YOUR ISSUE. NO WEAK TALK."
    }
]

@peacepal_app.before_request
def setup_session():
    session.setdefault("messages", copy.deepcopy(SIGMA_PROMPT))
    session.setdefault("previous_conversations", [])

@peacepal_app.route("/", methods=["GET", "POST"])
def peacepal():
    if request.method == "POST":
        user_input = request.form.get("user_input")
        target_lang = request.form.get("language", "en")
        
        if user_input.strip():
            try:
                # Translate input
                translated_input = translator.translate(user_input)
                session["messages"].append({"role": "user", "content": translated_input})
                
                # Generate response
                response = generate_response(session["messages"])
                session["messages"].append({"role": "assistant", "content": response})
                
                # Translate response
                if target_lang != "en":
                    translated_response = GoogleTranslator(source='en', target=target_lang).translate(response)
                    session["messages"][-1]["content"] = translated_response
                
                session.modified = True
            except Exception as e:
                flash("SYSTEM ERROR. FIX INPUT AND TRY AGAIN.", "error")

    # Structure conversations with IDs
    structured_convos = []
    for idx, conv in enumerate(session["previous_conversations"]):
        structured_convos.append({
            "id": idx,
            "title": conv.get("title", f"CONVO {idx+1}"),
            "messages": conv.get("messages", [])
        })

    return render_template("peacepal.html",
                         chat_history=[msg for msg in session["messages"] if msg["role"] != "system"],
                         previous_conversations=structured_convos)

def generate_response(messages):
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
        "max_tokens": 75,
        "temperature": 0.9,
        "frequency_penalty": 0.7
    }
    
    try:
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content'].upper()
    
    except Exception:
        return "SYSTEM ERROR. FOCUS ON WHAT YOU CAN CONTROL."

@peacepal_app.route("/load_conversation/<int:convo_id>")
def load_conversation(convo_id):
    if 0 <= convo_id < len(session["previous_conversations"]):
        session["messages"] = session["previous_conversations"][convo_id]["messages"]
        session.modified = True
    return redirect(url_for('peacepal_app.peacepal'))

@peacepal_app.route("/delete_conversation/<int:convo_id>")
def delete_conversation(convo_id):
    if 0 <= convo_id < len(session["previous_conversations"]):
        session["previous_conversations"].pop(convo_id)
        session.modified = True
        flash("CONVERSATION ERASED. WEAKNESS ELIMINATED.", "success")
    return redirect(url_for('peacepal_app.peacepal'))

@peacepal_app.route("/new_conversation")
def new_conversation():
    if session["messages"] != SIGMA_PROMPT:
        session["previous_conversations"].append({
            "id": len(session["previous_conversations"]),
            "title": f"GRINDSET {len(session['previous_conversations'])+1}",
            "messages": session["messages"]
        })
    session["messages"] = copy.deepcopy(SIGMA_PROMPT)
    session.modified = True
    return redirect(url_for('peacepal_app.peacepal'))

@peacepal_app.route("/clear_chat")
def clear_chat():
    session["messages"] = copy.deepcopy(SIGMA_PROMPT)
    session.modified = True
    return redirect(url_for('peacepal_app.peacepal'))



