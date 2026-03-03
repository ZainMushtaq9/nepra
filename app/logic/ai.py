import os
from groq import Groq

# Initialize the Groq client
# Ensure GROQ_API_KEY is set in your .env
api_key = os.environ.get("GROQ_API_KEY")
client = None
if api_key:
    client = Groq(api_key=api_key)

# Define the system prompt once, so the model knows its persona
SYSTEM_PROMPT = """You are a legal expert specializing in the NEPRA (National Electric Power Regulatory Authority) Consumer Service Manual of Pakistan. 
Your job is to advise users on electricity billing issues, legal rights, fault determination (whether it is a consumer mistake or company fault), and application procedures.
Always cite the relevant chapters or rules from the NEPRA manual where applicable. 
Answer concisely, professionally, and in a way that is easy for a layman to understand.
Do not provide advice outside of electricity billing and NEPRA regulations."""

def generate_ai_response(user_message, chat_history=None):
    """
    Sends a message to the Groq LLaMA 3.3 70B model and returns the response.
    
    :param user_message: The current message from the user.
    :param chat_history: A list of previous dict messages [{"role": "user"/"assistant", "content": "..."}]
    :return: The string response from the AI.
    """
    if not client:
        return "I'm sorry, my AI backend is currently unconfigured. Please provide a Groq API Key."

    # Start with the system prompt
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    
    # Append history if provided so the model has conversational context
    if chat_history:
        messages.extend(chat_history)
        
    # Append the latest user query
    messages.append({"role": "user", "content": user_message})

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.3, # Lower temperature for more factual, legal-style answers
            max_tokens=800,
            top_p=1,
            stream=False,
            stop=None,
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Error calling Groq API: {e}")
        return "I apologize, but I am currently unable to connect to the legal database to generate a response. Please try again later."
