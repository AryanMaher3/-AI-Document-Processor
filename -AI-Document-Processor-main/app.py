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

# Azure credentials
VISION_KEY = "9CTd2qVrUkZkvTC9AB44vqrsSYFponfJm8Fi6KCZCxoZuuOK96KBJQQJ99BAACYeBjFXJ3w3AAAEACOGH83l"
VISION_ENDPOINT = "https://ai-102-project.cognitiveservices.azure.com/"
SPEECH_KEY = "9CTd2qVrUkZkvTC9AB44vqrsSYFponfJm8Fi6KCZCxoZuuOK96KBJQQJ99BAACYeBjFXJ3w3AAAEACOGH83l"
SPEECH_REGION = "eastus"

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
            cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def authenticate_user(username, password):
    """Authenticate a user with a username and password."""
    hashed_password = hash_password(password)
    with sqlite3.connect("app.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ? AND password_hash = ?", (username, hashed_password))
        return cursor.fetchone() is not None

# Azure setup
def initialize_vision_client():
    return ComputerVisionClient(VISION_ENDPOINT, CognitiveServicesCredentials(VISION_KEY))

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
        st.error(f"Error extracting text: {e}")
        return None

def synthesize_speech(text):
    """Converts text to speech using Azure Speech Service."""
    try:
        speech_config = speechsdk.SpeechConfig(
            subscription=SPEECH_KEY, 
            region=SPEECH_REGION
        )
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        audio_config = speechsdk.audio.AudioOutputConfig(filename=temp_file.name)

        speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"

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

# Initialize session state
def initialize_session_state():
    """Initialize Streamlit session state variables."""
    if "extracted_text" not in st.session_state:
        st.session_state["extracted_text"] = None
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
    if "username" not in st.session_state:
        st.session_state["username"] = None

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
        return

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

    # Restrict access if not logged in
    if not st.session_state["logged_in"]:
        st.warning("Please log in to access the application.")
        return

    # Main app features (restricted to logged-in users)
    st.markdown("## 🤖 AI Document Processor")
    st.markdown("Extract text from images and convert it to speech using Azure AI")

    uploaded_file = st.file_uploader("Upload an image containing text", type=["png", "jpg", "jpeg", "bmp"])

    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Image", use_column_width=True)

        vision_client = initialize_vision_client()

        if st.button("🔍 Extract Text"):
            with st.spinner("Processing image..."):
                uploaded_file.seek(0)
                st.session_state["extracted_text"] = extract_text_from_image(uploaded_file, vision_client)

        if st.session_state["extracted_text"]:
            st.text_area("Extracted Text", st.session_state["extracted_text"], height=250)

            if st.button("🔊 Convert to Speech"):
                with st.spinner("Generating speech..."):
                    audio_file = synthesize_speech(st.session_state["extracted_text"])
                    if audio_file:
                        try:
                            with open(audio_file, "rb") as f:
                                audio_bytes = f.read()
                            st.audio(audio_bytes, format="audio/wav")
                        except Exception as e:
                            st.error(f"Error reading audio file: {e}")
                        finally:
                            try:
                                os.unlink(audio_file)
                            except Exception as e:
                                st.error(f"Error removing temporary file: {e}")
        elif st.session_state["extracted_text"] is not None:
            st.error("No text could be extracted from the image.")

if __name__ == "__main__":
    main()
