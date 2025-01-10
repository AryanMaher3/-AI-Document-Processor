import os
from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from msrest.authentication import CognitiveServicesCredentials
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

load_dotenv()

VISION_KEY = os.getenv("AZURE_COMPUTER_VISION_KEY")
VISION_ENDPOINT = os.getenv("AZURE_COMPUTER_VISION_ENDPOINT")
SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY")
SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")

vision_client = ComputerVisionClient(VISION_ENDPOINT, CognitiveServicesCredentials(VISION_KEY))
speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)
speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)

image_folder = "images"
image_path = os.path.join(image_folder, "articledata1.jpg")

def extract_text_from_image(image_path):
    """Extracts text from an image using Azure Computer Vision."""
    try:
        with open(image_path, "rb") as image:
            result = vision_client.read_in_stream(image, raw=True)
            operation_location = result.headers["Operation-Location"]
            operation_id = operation_location.split("/")[-1]

        result = vision_client.get_read_result(operation_id)
        while result.status not in [OperationStatusCodes.succeeded, OperationStatusCodes.failed]:
            result = vision_client.get_read_result(operation_id)

        if result.status == OperationStatusCodes.succeeded:
            extracted_text = ""
            for read_result in result.analyze_result.read_results:
                for line in read_result.lines:
                    extracted_text += line.text + " "
            return extracted_text.strip()
        return None
    except Exception as e:
        print(f"Error extracting text: {e}")
        return None

def convert_text_to_speech(text):
    """Converts text to speech using Azure Speech Service."""
    if text:
        print(f"Extracted Text: {text}")
        print("Playing audio...")

        try:

            speech_config.speech_synthesis_voice_name = "en-US-StephenNeural"  
            

            result = speech_synthesizer.speak_text_async(text).get()  

            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                print("Speech synthesis completed successfully.")
            else:
                print(f"Speech synthesis failed: {result.error_details}")

        except Exception as e:
            print(f"Error during speech synthesis: {e}")
    else:
        print("No text extracted from the image.")

def main():
    print("Processing image...")
    extracted_text = extract_text_from_image(image_path)
    convert_text_to_speech(extracted_text)

if __name__ == "__main__":
    main()
