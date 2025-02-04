from flask import Flask, request, jsonify, render_template
import os
from dotenv import load_dotenv
import openai

# Load environment variables
load_dotenv()

# Configure OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

app = Flask(__name__)

def get_ai_response(message, conversation_history=[]):
    conversation_history.append({"role": "user", "content": message})
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": """You are a warm, empathetic songwriting assistant helping users create personalized love songs.

Objective:
Help users create a personalized, romantic love song that feels special and unique. Engage users warmly and empathetically, making the process collaborative.

Process Flow (follow this order strictly):
1. Ask for partner's name only
2. Ask for user's name and email only
3. Ask about their love story
4. Ask about song tone preference
5. Ask about personal touches
6. Create and share draft lyrics
7. Get feedback and refine
8. Confirm delivery

Guardrails:
- Always maintain respectful, positive tone
- Encourage customization and personalization
- Be inclusive of all relationships
- Provide gentle guidance when needed
- Keep lyrics loving and sweet"""},
                *conversation_history
            ]
        )
        ai_response = response.choices[0].message['content']
        conversation_history.append({"role": "assistant", "content": ai_response})
        return ai_response
    except Exception as e:
        print(f"OpenAI API error: {str(e)}")
        return "I apologize, but I encountered an error. Please try again."

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_message = request.json.get('message')
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400
        
        print(f"Received message: {user_message}")  # Debug print
        response = get_ai_response(user_message)
        print(f"AI response: {response}")  # Debug print
        return jsonify({'response': response})
    except Exception as e:
        import traceback
        print(f"Error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/test', methods=['GET'])
def test():
    return jsonify({'status': 'working'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)