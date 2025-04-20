import requests
import toml

def generate_coping_mechanisms(user_input):
    # Load API key from secrets.toml
    api_key = toml.load('key.toml')['api']['key']
    
    # Prepare the payload for the Groq API
    messages = [
        {"role": "system", "content": "You are a mental health assistant. Provide personalized coping mechanisms based on the user's input, and make them short and point wise and no markdown texts"},
        {"role": "user", "content": user_input}
    ]
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
        "max_tokens": 150,
        "temperature": 0.7
    }
    
    # Make the API request
    response = requests.post(
        'https://api.groq.com/openai/v1/chat/completions',
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'},
        json=payload
    )
    
    # Extract the response content
    if response.status_code == 200:
        content = response.json().get('choices', [{}])[0].get('message', {}).get('content', '')
        return content.strip()
    else:
        return "Failed to generate coping mechanisms. Please try again later."