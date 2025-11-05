import random
import os
import requests 
from flask import Flask, render_template, request, redirect, url_for, session

# --- Configuration and Data ---
app = Flask(__name__)

# IMPORTANT: NEVER use this default key in production. Use a Render Environment Variable instead.
# For deployment, remove this line and set SECRET_KEY in Render's dashboard.
app.secret_key = 'a_very_secret_key_for_hangman_game_123' 

MAX_LIVES = 6

# --- NEW API CONFIGURATION ---
# These values MUST be set as Environment Variables on Render!
# X_RAPIDAPI_KEY: Your unique key from RapidAPI
# X_RAPIDAPI_HOST: wordsapiv1.p.rapidapi.com
RAPIDAPI_KEY = os.environ.get('X_RAPIDAPI_KEY')
RAPIDAPI_HOST = os.environ.get('X_RAPIDAPI_HOST', 'wordsapiv1.p.rapidapi.com')

# The base endpoint for searching and fetching words.
# We will append '?' and parameters later.
EXTERNAL_WORD_API_URL = "https://wordsapiv1.p.rapidapi.com/words/"


# Hardcoded GENRE LIST: These will be used to query the API.
GENRE_LIST = [
    "Animals", 
    "Sports", 
    "Technology"
]


# Simplified ASCII art for the Hangman stages (0 to 6 misses)
HANGMAN_STAGES = [
    """
  +---+
  |   |
      |
      |
      |
      |
=========
""", 
    """
  +---+
  |   |
  O   |
      |
      |
      |
=========
""", 
    """
  +---+
  |   |
  O   |
  |   |
      |
      |
=========
""", 
    """
  +---+
  |   |
  O   |
 /|   |
      |
      |
=========
""", 
    """
  +---+
  |   |
  O   |
 /|\  |
      |
      |
=========
""", 
    """
  +---+
  |   |
  O   |
 /|\  |
 /    |
      |
=========
""", 
    """
  +---+
  |   |
  O   |
 /|\  |
 / \  |
      |
=========
"""
]


def get_word_from_api(genre):
    """
    Fetches a random word based on a given genre/topic using the WordsAPI.
    Uses exponential backoff for resilience against transient network errors.
    
    This function demonstrates how to call an external API with authentication headers.
    """
    
    # Mapping genres to API tags (words with definition topic)
    # The API query uses the 'topic' constraint.
    topic = genre.lower() 
    
    querystring = {
        "random": "true",
        "hasDetails": "definitions", # Ensure it has definitions to filter for topics
        "limit": "1",
        "letterPattern": "^[a-zA-Z]{5,10}$", # Filter for 5-10 letters to make the game fun
        "includeDefinition": "true"
    }
    
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }
    
    max_retries = 3
    base_delay = 1
    
    for attempt in range(max_retries):
        try:
            # We use the /words/ endpoint for random words with constraints
            response = requests.get(EXTERNAL_WORD_API_URL, headers=headers, params=querystring)
            response.raise_for_status() # Raises an HTTPError for bad responses (4xx or 5xx)
            
            data = response.json()
            
            # The API returns a dictionary with 'word' and 'results' list
            word = data.get('word', '').upper()
            
            # Simple check to ensure the word is valid and contains only letters
            if word and word.isalpha():
                # Check if the word definition includes the topic (approximate genre match)
                results = data.get('results', [])
                for result in results:
                    if topic in result.get('partOfSpeech', '').lower() or \
                       topic in result.get('definition', '').lower() or \
                       topic in result.get('topic', '').lower() or \
                       topic in ' '.join(result.get('synonyms', [])).lower():
                        return word
                
                # Fallback: if topic filtering is too strict, just return the random word found
                return word 

            print(f"API returned an invalid word: {data}")
            return None

        except requests.exceptions.RequestException as e:
            print(f"API request failed on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                import time
                delay = base_delay * (2 ** attempt)
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print("Max retries reached. Using fallback word.")
                break
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            break
            
    # Fallback if API fails: pick a hardcoded word (only if API Key is missing or failed)
    fallback_words = {
        "animals": "ELEPHANT", "sports": "SOCCER", "technology": "PYTHON"
    }
    return fallback_words.get(topic, "GEMINI")


def get_display_word(word, guessed_letters):
    """Returns the word with unguessed letters replaced by underscores."""
    display = ""
    for letter in word:
        if letter in guessed_letters:
            display += letter + " "
        else:
            display += "_ "
    return display.strip()

def initialize_game(genre):
    """Initializes a new game session."""
    word_to_guess = get_word_from_api(genre)
    
    session.clear()
    session['word'] = word_to_guess
    session['guessed_letters'] = []
    session['lives'] = MAX_LIVES
    session['current_genre'] = genre
    session['message'] = f"New game started! Guess the {genre} word."
    
    print(f"New word to guess: {word_to_guess} (Genre: {genre})")

@app.route('/', methods=['GET', 'POST'])
def index():
    """
    Main route for displaying the game state and handling user input.
    Handles both letter guesses and genre selection/new game starts.
    """
    
    # Check if a new game needs to be initialized (either no word in session or genre change)
    if 'word' not in session or request.form.get('genre_select'):
        genre = request.form.get('genre_select') or GENRE_LIST[0]
        initialize_game(genre)

    # State variables from session
    word_to_guess = session.get('word').upper()
    lives = session.get('lives')
    guessed_letters = session.get('guessed_letters', [])
    current_genre = session.get('current_genre')
    is_game_over = False
    
    # Convert list of guessed letters to a set for efficient lookup
    guessed_set = set(guessed_letters)

    # 1. Handle POST requests (Letter Guess or Genre Change)
    if request.method == 'POST':
        letter = request.form.get('letter', '').upper()
        
        # --- Handle Letter Guess Input ---
        if letter and letter.isalpha() and len(letter) == 1 and not is_game_over:
            
            if letter in guessed_set:
                session['message'] = f"**{letter}** already guessed. Try again!"
            elif letter in word_to_guess:
                guessed_set.add(letter)
                session['message'] = f"Correct guess: **{letter}**!"
            else:
                guessed_set.add(letter)
                session['lives'] = lives - 1
                session['message'] = f"Incorrect guess. **{letter}** is not in the word."
        
        elif letter: # Handle invalid input for a guess
            session['message'] = "Invalid input. Please enter a single letter (A-Z)."

        # Convert the set back to a list before saving to the session
        session['guessed_letters'] = list(guessed_set)

        # Re-fetch updated state for rendering after POST
        lives = session.get('lives')
    
    # 2. Update display word and check for Win/Loss state
    display_word = get_display_word(word_to_guess, guessed_set)
    is_win = "_" not in display_word
    is_loss = lives <= 0
    
    message = session.get('message', "")
    
    if is_win:
        is_game_over = True
        message = f"🎉 YOU WON! The word was **{word_to_guess}**."
    elif is_loss:
        is_game_over = True
        message = f"💀 GAME OVER. The word was **{word_to_guess}**."

    # 3. Render the template with the current state
    lives_index = MAX_LIVES - lives
    
    return render_template(
        'index.html',
        display_word=display_word,
        lives=lives,
        message=message,
        guessed_letters=sorted(list(guessed_set)), 
        is_game_over=is_game_over,
        hangman_art=HANGMAN_STAGES[lives_index],
        max_lives=MAX_LIVES,
        genres=GENRE_LIST,
        current_genre=current_genre
    )

@app.route('/restart')
def restart():
    """Restarts the game with the current genre."""
    current_genre = session.get('current_genre', GENRE_LIST[0])
    initialize_game(current_genre)
    return redirect(url_for('index'))

if __name__ == '__main__':
    # When running locally, you can use the built-in Flask server
    # Note: On Render, gunicorn will run the app
    app.run(debug=True)