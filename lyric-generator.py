from flask import Flask, request, jsonify, render_template
import os
from dotenv import load_dotenv
import openai
import sqlite3
from datetime import datetime
import razorpay
from flask import redirect, url_for

# Load environment variables
load_dotenv()

# Configure OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

app = Flask(__name__)

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
                  email TEXT,
                  lyric_content TEXT,
                  payment_id TEXT,
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
8. When user confirms lyrics are final, ALWAYS respond with the following format exactly:

FINAL_LYRICS_START
[Partner Name]: {partner_name}
[User Name]: {user_name}
[Email]: {email}
[Lyrics]:
{the complete final lyrics}
FINAL_LYRICS_END

Then add your farewell message.

Guardrails:
- Always maintain respectful, positive tone
- Encourage customization and personalization
- Be inclusive of all relationships
- Provide gentle guidance when needed
- Keep lyrics loving and sweet
- ALWAYS use the FINAL_LYRICS markers when user confirms lyrics are final"""},
                *conversation_history
            ]
        )
        ai_response = response.choices[0].message['content']
        conversation_history.append({"role": "assistant", "content": ai_response})
        
        # Check if this is a final lyrics response
        if "FINAL_LYRICS_START" in ai_response and "FINAL_LYRICS_END" in ai_response:
            try:
                # Extract the lyrics data
                lyrics_text = ai_response.split("FINAL_LYRICS_START")[1].split("FINAL_LYRICS_END")[0].strip()
                
                # Parse the lyrics data
                partner_name = lyrics_text.split("[Partner Name]:")[1].split("\n")[0].strip()
                user_name = lyrics_text.split("[User Name]:")[1].split("\n")[0].strip()
                email = lyrics_text.split("[Email]:")[1].split("\n")[0].strip()
                lyrics = lyrics_text.split("[Lyrics]:")[1].strip()
                
                # Save to database
                save_lyric(user_name, partner_name, email, lyrics)
                print(f"Saved lyrics to database for {user_name} and {partner_name}")
                
                # Remove the markers from the response
                ai_response = "Great! I've saved your finalized lyrics. You can expect them to be delivered to your email shortly! Is there anything else you'd like to know?"
            except Exception as e:
                print(f"Error saving lyrics: {str(e)}")
                print(f"Lyrics text was: {lyrics_text}")
        
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
        
        print(f"Received message: {user_message}")
        response = get_ai_response(user_message)
        print(f"AI response: {response}")
        return jsonify({'response': response})
    except Exception as e:
        import traceback
        print(f"Error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)