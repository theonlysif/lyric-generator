from agno.agent import Agent
from agno.models.openai import OpenAIChat
from flask import Flask, request, jsonify, render_template
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Check for API key
if not os.getenv('OPENAI_API_KEY'):
    raise ValueError("OPENAI_API_KEY not found in environment variables")

app = Flask(__name__)

love_song_agent = Agent(
    model=OpenAIChat(
        id="gpt-4",
        api_key=os.getenv('OPENAI_API_KEY')
    ),
    # Reduce memory to prevent context overflow
    add_history_to_messages=True,
    num_history_responses=3,  # Reduced from 5 to 3
    description="""You are a warm, empathetic songwriting assistant helping users create personalized love songs.

Objective:
Help users create a personalized, romantic love song that feels special and unique. Engage users warmly and empathetically, making the process collaborative.

IMPORTANT: You have memory and should remember information the user has already shared. Never ask for information they've already given you.

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
- Keep lyrics loving and sweet""",
    markdown=True,
)

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
        # Run the agent with the message and get the response
        response = love_song_agent.run(user_message)
        # Extract just the content from the RunResponse object
        response_content = response.content if response else "Sorry, I couldn't process that message"
        print(f"Agent response: {response_content}")  # Debug print
        return jsonify({'response': response_content})
    except Exception as e:
        import traceback
        print(f"Error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/test', methods=['GET'])
def test():
    return jsonify({'status': 'working'})

# Modify the run configuration to work with production servers
if __name__ == '__main__':
    # Use environment variable for port if available (for production)
    port = int(os.environ.get('PORT', 5001))
    # In production, host should be '0.0.0.0'
    app.run(host='0.0.0.0', port=port)