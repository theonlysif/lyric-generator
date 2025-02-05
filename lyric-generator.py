from flask import Flask, request, jsonify, render_template, session
import os
from dotenv import load_dotenv
import openai
import sqlite3
from datetime import datetime
import razorpay
from flask import redirect, url_for
import secrets
import json

# Load environment variables
load_dotenv()

# Configure OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')
print(f"OpenAI API Key Loaded: {openai.api_key is not None}")  # Debugging statement

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')
app.config["SESSION_PERMANENT"] = False  # Make session temporary
app.config["SESSION_TYPE"] = "filesystem"  # Or set to "null" for in-memory

# Add Razorpay configuration
razorpay_client = razorpay.Client(
    auth=(os.getenv('RAZORPAY_KEY_ID'), os.getenv('RAZORPAY_KEY_SECRET'))
)

# Database setup
def init_db():
    conn = sqlite3.connect('lyrics.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS lyrics
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_name TEXT,
                  partner_name TEXT,
                  language_vibe TEXT,
                  story TEXT,
                  descriptive_words TEXT,
                  mood TEXT,
                  musical_style TEXT,
                  conversation_history TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS payments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  order_id TEXT,
                  payment_id TEXT,
                  amount INTEGER,
                  status TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

def save_lyric(user_name, partner_name, email, lyric_content):
    conn = sqlite3.connect('lyrics.db')
    c = conn.cursor()
    c.execute('''INSERT INTO lyrics (user_name, partner_name, email, lyric_content)
                 VALUES (?, ?, ?, ?)''', (user_name, partner_name, email, lyric_content))
    conn.commit()
    conn.close()

def collect_song_details(message, conversation_history=[]):
    conversation_history.append({"role": "user", "content": message})
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": """
                You are a Song Detail Collector. Your mission is to gather specific details from the user to craft a personalized love song. Engage the user in a friendly and empathetic manner, ensuring the conversation is enjoyable and informative.

                Objective:
                - Collect the following details:
                  1. User's name
                  2. Partner's name
                  3. Preferred language vibe ('Hindi', 'English', or 'Mix')
                  4. A memorable story or moment to capture in the song
                  5. Descriptive words/phrases about the partner
                  6. Desired mood or feeling for the song
                  7. Musical style or artist inspiration

                Guidelines:
                - Keep the tone cool, friendly, and engaging.
                - Encourage the user to share details by asking open-ended questions.
                - Provide gentle guidance to help the user articulate their thoughts.
                - Avoid providing extra information or commentary unrelated to the task.
                - Ensure the user feels heard and valued throughout the interaction.
                """},
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
    user_message = request.json.get('message')
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400
    
    # Initialize conversation history for each session
    if 'conversation_history' not in session:
        session['conversation_history'] = []
    
    conversation_history = session['conversation_history']
    response = collect_song_details(user_message, conversation_history)
    
    # Save conversation history in session
    session['conversation_history'] = conversation_history
    
    return jsonify({'response': response})

@app.route('/test', methods=['GET'])
def test():
    return jsonify({'status': 'working'})

# Admin route to view saved lyrics (protect this in production!)
@app.route('/admin/lyrics', methods=['GET'])
def view_lyrics():
    conn = sqlite3.connect('lyrics.db')
    c = conn.cursor()
    c.execute('SELECT * FROM lyrics ORDER BY created_at DESC')
    lyrics = c.fetchall()
    conn.close()
    
    # Convert to list of dictionaries for easier templating
    lyrics_list = [
        {
            'id': l[0],
            'user_name': l[1],
            'partner_name': l[2],
            'email': l[3],
            'lyric_content': l[4],
            'created_at': l[5]
        }
        for l in lyrics
    ]
    
    return render_template('admin.html', lyrics=lyrics_list)

# Add payment routes
@app.route('/create-order', methods=['POST'])
def create_order():
    try:
        amount = 99900  # ₹999 in paise
        currency = 'INR'
        
        # Create Razorpay Order
        payment_data = {
            'amount': amount,
            'currency': currency,
            'payment_capture': '1'
        }
        
        order = razorpay_client.order.create(data=payment_data)
        return jsonify({
            'order_id': order['id'],
            'amount': amount,
            'currency': currency,
            'key': os.getenv('RAZORPAY_KEY_ID')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/payment-callback', methods=['POST'])
def payment_callback():
    try:
        # Verify payment signature
        params_dict = {
            'razorpay_payment_id': request.form.get('razorpay_payment_id'),
            'razorpay_order_id': request.form.get('razorpay_order_id'),
            'razorpay_signature': request.form.get('razorpay_signature')
        }
        
        razorpay_client.utility.verify_payment_signature(params_dict)
        
        # Payment successful, store in database
        save_payment(
            order_id=request.form.get('razorpay_order_id'),
            payment_id=request.form.get('razorpay_payment_id'),
            amount=request.form.get('amount')
        )
        
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def save_payment(order_id, payment_id, amount):
    conn = sqlite3.connect('lyrics.db')
    c = conn.cursor()
    c.execute('''INSERT INTO payments (order_id, payment_id, amount, status)
                 VALUES (?, ?, ?, ?)''', (order_id, payment_id, amount, 'success'))
    conn.commit()
    conn.close()

def send_samples():
    # Sample data for demonstration
    samples = [
        {"name": "Reference 1", "description": "A romantic ballad with a soft melody.", "audio_url": "/static/audio/sample1.mp3"},
        {"name": "Reference 2", "description": "An upbeat pop song with catchy lyrics.", "audio_url": "/static/audio/sample2.mp3"},
        {"name": "Reference 3", "description": "A soulful jazz piece with smooth vocals.", "audio_url": "/static/audio/sample3.mp3"}
    ]
    
    # Create messages for each sample
    messages = []
    for sample in samples:
        messages.append(f"Reference: {sample['name']}\nDescription: {sample['description']}")
        messages.append({"audio": sample["audio_url"]})
    
    # Add a prompt for the user to choose a reference
    messages.append("Please choose a reference you like and keep in mind the way the prompt was written to get the desired result.")
    
    return messages

def save_conversation_to_db(user_name, partner_name, language_vibe, story, descriptive_words, mood, musical_style, conversation_history):
    conn = sqlite3.connect('lyrics.db')
    c = conn.cursor()
    c.execute('''INSERT INTO lyrics (user_name, partner_name, language_vibe, story, descriptive_words, mood, musical_style, conversation_history)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
              (user_name, partner_name, language_vibe, story, descriptive_words, mood, musical_style, conversation_history))
    conn.commit()
    conn.close()

@app.route('/submit', methods=['POST'])
def submit():
    data = request.json
    save_conversation_to_db(
        data.get('user_name'),
        data.get('partner_name'),
        data.get('language_vibe'),
        data.get('story'),
        data.get('descriptive_words'),
        data.get('mood'),
        data.get('musical_style'),
        json.dumps(session.get('conversation_history', []))
    )
    return jsonify({'status': 'success'})

@app.route('/clear_session', methods=['POST'])
def clear_session():
    session.clear()
    return jsonify({'status': 'session cleared'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)