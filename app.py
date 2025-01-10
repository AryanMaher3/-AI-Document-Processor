import streamlit as st
import os
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

# Custom CSS
def local_css():
    st.markdown("""
        <style>
        /* Add custom styling here */
        </style>
    """, unsafe_allow_html=True)

# Initialize Azure clients
try:
    vision_client = ComputerVisionClient(
        VISION_ENDPOINT, 
        CognitiveServicesCredentials(VISION_KEY)
    )
except Exception as e:
    st.error(f"Error initializing Vision client: {e}")

def extract_text_from_image(image_file):
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

def initialize_session_state():
    """Initialize Streamlit session state variables."""
    if "extracted_text" not in st.session_state:
        st.session_state["extracted_text"] = None

def main():
    st.set_page_config(
        page_title="AI Document Processor",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Apply custom CSS
    local_css()
    
    # Initialize session state
    initialize_session_state()
    
    # Custom title section
    st.markdown("## 🤖 AI Document Processor")
    st.markdown("Extract text from images and convert it to speech using Azure AI")

    # Add sidebar
    st.sidebar.markdown("### How to Use")
    st.sidebar.write("""
        1. Upload an image containing text
        2. Click 'Extract Text' to process
        3. Review the extracted text
        4. Click 'Convert to Speech' to hear it
    """)

    # Main content
    uploaded_file = st.file_uploader("Upload an image containing text", type=["png", "jpg", "jpeg", "bmp"])
    
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Image", use_column_width=True)

        if st.button("🔍 Extract Text"):
            with st.spinner("Processing image..."):
                uploaded_file.seek(0)
                st.session_state["extracted_text"] = extract_text_from_image(uploaded_file)
        
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
