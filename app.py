import streamlit as st
import os
import sqlite3
import hashlib
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from msrest.authentication import CognitiveServicesCredentials
import azure.cognitiveservices.speech as speechsdk
import tempfile
from PIL import Image
import io
import time
from datetime import datetime

# Azure credentials
VISION_KEY = "9CTd2qVrUkZkvTC9AB44vqrsSYFponfJm8Fi6KCZCxoZuuOK96KBJQQJ99BAACYeBjFXJ3w3AAAEACOGH83l"
VISION_ENDPOINT = "https://ai-102-project.cognitiveservices.azure.com/"
SPEECH_KEY = "9CTd2qVrUkZkvTC9AB44vqrsSYFponfJm8Fi6KCZCxoZuuOK96KBJQQJ99BAACYeBjFXJ3w3AAAEACOGH83l"
SPEECH_REGION = "eastus"

# List of available voices
AVAILABLE_VOICES = [
    "en-US-JennyNeural",  # Female American English
    "en-US-GuyNeural",    # Male American English
    "en-GB-SoniaNeural",  # Female British English
    "en-AU-NatashaNeural", # Female Australian English
    "de-DE-KatjaNeural",  # Female German
    "fr-FR-DeniseNeural", # Female French
]

# Constants for file storage
USER_STORAGE_DIR = "user_storage"
MAX_HISTORY_ITEMS = 10

# Database helper functions
def hash_password(password):
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

def add_user(username, password):
    """Add a new user to the database."""
    hashed_password = hash_password(password)
    with sqlite3.connect("app.db") as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", 
                         (username, hashed_password))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def authenticate_user(username, password):
    """Authenticate a user with a username and password."""
    hashed_password = hash_password(password)
    with sqlite3.connect("app.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password_hash = ?", 
                      (username, hashed_password))
        return cursor.fetchone() is not None

def ensure_user_directory(username):
    """Create user directory if it doesn't exist."""
    user_dir = os.path.join(USER_STORAGE_DIR, username)
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)
    return user_dir

def save_uploaded_file(uploaded_file, username):
    """Save uploaded file to user's directory with timestamp."""
    if uploaded_file is None:
        return None
    
    user_dir = ensure_user_directory(username)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_extension = os.path.splitext(uploaded_file.name)[1]
    filename = f"{timestamp}{file_extension}"
    file_path = os.path.join(user_dir, filename)
    
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    # Add entry to database
    with sqlite3.connect("app.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_files (username, filename, original_filename, upload_date)
            VALUES (?, ?, ?, datetime('now'))
        """, (username, filename, uploaded_file.name))
    
    return file_path

def get_user_history(username):
    """Get user's file upload history."""
    with sqlite3.connect("app.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT filename, original_filename, upload_date, extracted_text
            FROM user_files
            WHERE username = ?
            ORDER BY upload_date DESC
            LIMIT ?
        """, (username, MAX_HISTORY_ITEMS))
        return cursor.fetchall()

def update_extracted_text(username, filename, text):
    """Update the extracted text for a file in the database."""
    with sqlite3.connect("app.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE user_files
            SET extracted_text = ?
            WHERE username = ? AND filename = ?
        """, (text, username, filename))

# Azure setup functions
def initialize_vision_client():
    """Initialize the Computer Vision client."""
    try:
        vision_client = ComputerVisionClient(
            VISION_ENDPOINT, 
            CognitiveServicesCredentials(VISION_KEY)
        )
        return vision_client
    except Exception as e:
        st.error(f"Error initializing vision client: {e}")
        return None

def extract_text_from_image(image_file, vision_client):
    """Extracts text from an image using Azure Computer Vision."""
    try:
        image_bytes = io.BytesIO(image_file.read())
        image_bytes.seek(0)

        result = vision_client.read_in_stream(image_bytes, raw=True)
        operation_location = result.headers["Operation-Location"]
        operation_id = operation_location.split("/")[-1]

        result = vision_client.get_read_result(operation_id)
        while result.status not in [OperationStatusCodes.succeeded, OperationStatusCodes.failed]:
            time.sleep(1)
            result = vision_client.get_read_result(operation_id)

        if result.status == OperationStatusCodes.succeeded:
            extracted_text = ""
            for read_result in result.analyze_result.read_results:
                for line in read_result.lines:
                    extracted_text += line.text + "\n"
            return extracted_text.strip()
        return None
    except Exception as e:
        st.error(f"Error extracting text: {str(e)}")
        return None

def synthesize_speech(text, voice_name):
    """Converts text to speech using Azure Speech Service with selected voice."""
    try:
        speech_config = speechsdk.SpeechConfig(
            subscription=SPEECH_KEY, 
            region=SPEECH_REGION
        )
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        audio_config = speechsdk.audio.AudioOutputConfig(filename=temp_file.name)

        speech_config.speech_synthesis_voice_name = voice_name

        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, 
            audio_config=audio_config
        )

        result = synthesizer.speak_text_async(text).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            st.success("Speech synthesis completed successfully!")
            return temp_file.name
        else:
            st.error("Speech synthesis failed")
            return None
    except Exception as e:
        st.error(f"Error in speech synthesis: {str(e)}")
        return None

def initialize_session_state():
    """Initialize Streamlit session state variables."""
    if "extracted_text" not in st.session_state:
        st.session_state["extracted_text"] = None
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
    if "username" not in st.session_state:
        st.session_state["username"] = None
    if "selected_voice" not in st.session_state:
        st.session_state["selected_voice"] = AVAILABLE_VOICES[0]

def main():
    st.set_page_config(
        page_title="AI Document Processor",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Initialize session state
    initialize_session_state()

    # User Authentication Section
    st.sidebar.title("User Authentication")

    auth_mode = st.sidebar.radio("Choose mode:", ["Login", "Signup"])

    if auth_mode == "Signup":
        st.sidebar.subheader("Create an Account")
        new_username = st.sidebar.text_input("Username", key="signup_username")
        new_password = st.sidebar.text_input("Password", type="password", key="signup_password")
        if st.sidebar.button("Signup"):
            if add_user(new_username, new_password):
                st.sidebar.success("Account created successfully!")
            else:
                st.sidebar.error("Username already exists.")

    elif auth_mode == "Login":
        st.sidebar.subheader("Login to Your Account")
        username = st.sidebar.text_input("Username", key="login_username")
        password = st.sidebar.text_input("Password", type="password", key="login_password")
        if st.sidebar.button("Login"):
            if authenticate_user(username, password):
                st.sidebar.success(f"Welcome, {username}!")
                st.session_state["logged_in"] = True
                st.session_state["username"] = username
            else:
                st.sidebar.error("Invalid username or password.")
                st.session_state["logged_in"] = False

    # Main app features (restricted to logged-in users)
    if st.session_state["logged_in"]:
        st.markdown("## 🤖 AI Document Processor")
        
        # Add tabs for upload and history
        tab1, tab2 = st.tabs(["Upload New Image", "History"])
        
        with tab1:
            st.markdown("Extract text from images and convert it to speech using Azure AI")
            
            uploaded_file = st.file_uploader("Upload an image containing text", type=["png", "jpg", "jpeg", "bmp"])
            
            if uploaded_file:
                # Save the uploaded file
                file_path = save_uploaded_file(uploaded_file, st.session_state["username"])
                
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded Image", use_column_width=True)
                
                vision_client = initialize_vision_client()
                
                if st.button("🔍 Extract Text"):
                    with st.spinner("Processing image..."):
                        uploaded_file.seek(0)
                        extracted_text = extract_text_from_image(uploaded_file, vision_client)
                        st.session_state["extracted_text"] = extracted_text
                        
                        # Update database with extracted text
                        if extracted_text:
                            filename = os.path.basename(file_path)
                            update_extracted_text(st.session_state["username"], filename, extracted_text)
                
                if st.session_state.get("extracted_text"):
                    st.text_area("Extracted Text", st.session_state["extracted_text"], height=250)
                    
                    # Add voice selection dropdown
                    selected_voice = st.selectbox("Choose Voice", AVAILABLE_VOICES, 
                                                index=AVAILABLE_VOICES.index(st.session_state["selected_voice"]))
                    st.session_state["selected_voice"] = selected_voice

                    if st.button("🔊 Convert to Speech"):
                        with st.spinner("Generating speech..."):
                            audio_file = synthesize_speech(st.session_state["extracted_text"], selected_voice)
                            if audio_file:
                                try:
                                    with open(audio_file, "rb") as f:
                                        audio_bytes = f.read()
                                    st.audio(audio_bytes, format="audio/wav")
                                finally:
                                    try:
                                        os.unlink(audio_file)
                                    except Exception as e:
                                        st.error(f"Error removing temporary file: {e}")
        
        with tab2:
            st.markdown("### Previous Uploads")
            history = get_user_history(st.session_state["username"])
            
            if not history:
                st.info("No previous uploads found.")
            else:
                for filename, original_filename, upload_date, extracted_text in history:
                    with st.expander(f"{original_filename} (Uploaded: {upload_date})"):
                        file_path = os.path.join(USER_STORAGE_DIR, st.session_state["username"], filename)
                        if os.path.exists(file_path):
                            img = Image.open(file_path)
                            st.image(img, caption=original_filename, use_column_width=True)
                            
                            if extracted_text:
                                st.text_area("Extracted Text", extracted_text, height=100)
                                
                                # Add voice selection for historical items
                                selected_voice = st.selectbox(
                                    "Choose Voice", 
                                    AVAILABLE_VOICES,
                                    key=f"voice_{filename}"
                                )

                                if st.button("🔊 Convert to Speech", key=f"speech_{filename}"):
                                    with st.spinner("Generating speech..."):
                                        audio_file = synthesize_speech(extracted_text, selected_voice)
                                        if audio_file:
                                            try:
                                                with open(audio_file, "rb") as f:
                                                    audio_bytes = f.read()
                                                st.audio(audio_bytes, format="audio/wav")
                                            finally:
                                                try:
                                                    os.unlink(audio_file)
                                                except Exception:
                                                    pass
                        else:
                            st.error("Image file not found.")
    else:
        st.warning("Please log in to access the application.")

if __name__ == "__main__":
    main()