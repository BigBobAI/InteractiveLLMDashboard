import os
os.environ["STREAMLIT_DEVELOPMENT_MODE"] = "false"
os.environ["STREAMLIT_DEV_MODE"] = "0"
os.environ["STREAMLIT_WATCHER_TYPE"] = "none"
os.environ["STREAMLIT_SERVER_PORT"] = "8501"
os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"

import sys
import io
import uuid
import tempfile
import subprocess
import threading
import queue
import re
import config 
import requests
import streamlit as st #in venv --> pip install streamlit
import ollama #in venv --> pip install ollama
from streamlit_mic_recorder import mic_recorder
from faster_whisper import WhisperModel
from pypdf import PdfReader #in venv --> pip install pypdf
import pandas as pd #in venv --> pip install pandas, pip install tabulate
from docx import Document #in venv --> pip install python-docx
from docling.document_converter import DocumentConverter

#also note, for installations you should also be able to do pip install -r requirements.txt (all of the requirements should be in there)


#docling testing --> remove after research is finished
#source = "https://arxiv.org/pdf/2408.09869" --> where the file is coming from
#converter = DocumentConverter() --> converter
#doc = converter.convert(source).document --> convert the file into a docling document
#print(doc.export_to_markdown()) --> output the document


if __name__ == "__main__":

    st.set_page_config(layout="wide")

    #define the standard initial messages for a new chat
    INITIAL_CHAT_HISTORY = [
        {"role": "system", "content": config.SYSTEM_MESSAGE},
        {'role': 'assistant', 'content': 'Hello! I am Bob. Please let me know how I can best assist you today.'}
    ]

    #function to find the path of the file that it is given (note: MEIPASS is the temporary folder pyinstaller makes, which is why we need this)
    def find_path(file_path):
        if hasattr(sys, "_MEIPASS"):
            return os.path.join(sys._MEIPASS, file_path) #return the pyinstaller path
        return os.path.join(os.path.abspath("."), file_path) #return the current directory path plus the given file path

    #function to load the css styling, takes the file path for the css, finds it, loads it/shows it
    def load_css(css_path):
        with open(find_path(css_path)) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    #call the function to load the styling
    load_css("Styling/bobStyle.css") 

    #creates a unique key for each chat message (made this for styling)
    def unique_message(name):
        return st.container(key=f"{name}-{uuid.uuid4()}")

    MODEL = 'llava:7b' #this is the model we are using,  if you don't already have this on your computer in terminal do: ollama run llava:7b

    def warmup_model(): #warmup function to start the model before the user inputs anything, this is to reduce the wait time for the first response
        try:
            requests.post(
                "http://localhost:11434/api/chat",
                json={"model": MODEL},
                timeout=30
            )
        except:
            pass


    # --- Session State Initialization---
    if 'MODEL_WARMED_UP' not in st.session_state:
        with st.spinner("Warming up Big Bob... This may take a moment."): #warmup message while the model is starting
            warmup_model()
        st.session_state['MODEL_WARMED_UP'] = True


    if 'CHATS' not in st.session_state:
        #CHATS is a list of chat histories (list of lists of dictionaries)
        st.session_state['CHATS'] = [INITIAL_CHAT_HISTORY.copy()] 
        st.session_state['CHAT_NAMES'] = ["Chat 1"]
        st.session_state.current_chat = 0
        st.session_state.selected_chat = 0

    if "messages" not in st.session_state:
        st.session_state.messages = st.session_state['CHATS'][st.session_state.current_chat].copy()

    #voice-mode state
    if "voice_mode" not in st.session_state:
        st.session_state.voice_mode = True
    if "auto_speak" not in st.session_state:
        st.session_state.auto_speak = True
    if "mic_cycle" not in st.session_state:
        st.session_state.mic_cycle = 0

    if "tts_queue" not in st.session_state:
        st.session_state.tts_queue = queue.Queue()
    
    if "tts_worker_started" not in st.session_state:
        st.session_state.tts_worker_started = False

    def _tts_worker(q: queue.Queue):
        while True:
            text = q.get()
            if text is None:
                break
            text = text.strip()
            if not text:
                continue
            subprocess.Popen(["say", text])

    def ensure_tts_worker_running():
        if not st.session_state.tts_worker_started:
            t = threading.Thread(target=_tts_worker, args=(st.session_state.tts_queue,), daemon=True)
            t.start()
            st.session_state.tts_worker_started = True
    
    def enqueue_tts(text: str):
    # avoid speaking tiny fragments
        if text and len(text.strip()) >= 2:
            st.session_state.tts_queue.put(text.strip())

    def get_whisper_model(): #cache whisper model so loads once not 10x times
        return WhisperModel("base", device="cpu", compute_type="int8")
    
    def transcribe_audio_to_text(wav_bytes: bytes) -> str:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name

        whisper_model = get_whisper_model()
        segments, _info = whisper_model.transcribe(tmp_path, vad_filter=True)
        text = " ".join(seg.text.strip() for seg in segments).strip()
        return text

    def tts_to_wav_bytes(text: str) -> bytes | None:
        text = (text or "").strip()
        if not text:
            return None
        
        try:
            import pyttsx3  # pip install pyttsx3
            engine = pyttsx3.init()
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as out_wav:
                out_path = out_wav.name

            engine.save_to_file(text, out_path)
            engine.runAndWait()

            with open(out_path, "rb") as f:
                return f.read()
        except Exception:
            pass

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".aiff") as out_aiff:
                aiff_path = out_aiff.name
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as out_wav:
                wav_path = out_wav.name

            subprocess.run(["say", "-o", aiff_path, text], check=True)
            subprocess.run(["afconvert", aiff_path, "-f", "WAVE", "-d", "LEI16", wav_path], check=True)

            with open(wav_path, "rb") as f:
                return f.read()
        except Exception:
            return None

    # --- Chat Management Functions---

    #create our clear all chats function
    def clear_all_chats():
        st.session_state['CHATS'] = [INITIAL_CHAT_HISTORY.copy()]
        st.session_state['CHAT_NAMES'] = ['Chat 1']
        st.session_state.messages = st.session_state['CHATS'][0].copy()
        st.session_state.current_chat = 0
        st.session_state.selected_chat = 0

    #create our new chat function
    def new_chat():
        #save the history of the current chat before switching away
        st.session_state['CHATS'][st.session_state.current_chat] = st.session_state.messages

        #prepare the new chat
        CHAT_COUNT = len(st.session_state['CHAT_NAMES'])
        CHAT_NAME = "Chat " + str(CHAT_COUNT+1)
        
        #append a new, complete chat history (a list of dictionaries)
        st.session_state['CHATS'].append(INITIAL_CHAT_HISTORY.copy()) 
        st.session_state['CHAT_NAMES'].append(CHAT_NAME)
        
        #switch to the new chat
        new_chat_index = len(st.session_state['CHAT_NAMES']) - 1
        st.session_state.current_chat = new_chat_index
        st.session_state.selected_chat = new_chat_index
        st.session_state.messages = st.session_state['CHATS'][new_chat_index]

    #create our chat switching function
    def chat_switch(target_chat):
        #save the history of the chat we are leaving
        st.session_state['CHATS'][st.session_state.current_chat] = st.session_state.messages
        
        #update current_chat index to new chat index
        st.session_state.current_chat = target_chat
        st.session_state.selected_chat = target_chat

        #load the history of the chat we are switching to
        st.session_state.messages = st.session_state['CHATS'][target_chat]

    def delete_chat(chat_index: int):
        if len(st.session_state['CHATS']) <= 1:
            st.warning("You can't delete the last remaining chat.")
            return
            
        st.session_state['CHATS'].pop(chat_index) #remove the chat history at the given index
        st.session_state['CHAT_NAMES'].pop(chat_index) #remove the chat name at the given index

        if chat_index < st.session_state.current_chat:
            st.session_state.current_chat -= 1

        if chat_index == st.session_state.current_chat:
            if st.session_state.current_chat >= len(st.session_state['CHATS']):
                st.session_state.current_chat = len(st.session_state['CHATS']) -1
            st.session_state.selected_chat = st.session_state.current_chat
            st.session_state.messages = st.session_state['CHATS'][st.session_state.current_chat].copy()
            st.rerun()


    #initializes the messages for the current view
    if 'messages' not in st.session_state:
        #initialize messages with the first chat's history
        st.session_state.messages = st.session_state['CHATS'][st.session_state.current_chat].copy()

    # --- Message Display Loop ---

    #set the avatars for the user and assistant (this is important for making the exe)
    user_avatar = find_path("Assets/User_Icon.png")
    assistant_avatar = find_path("Assets/smiley.jpg")

    #for all the messages we have in the session state --> display the message content
    for message in st.session_state["messages"]:
        #Check if the message is a dictionary
        if isinstance(message, dict) and message["role"] != "system":
            #if role is user display user avatar and put in container
            if(message["role"] == "user"):
                with unique_message("user"):
                    with st.chat_message("user", avatar=user_avatar):
                        st.markdown(message["content"])
        
            else:
            #if role is assistant display assistant avatar
                with st.chat_message("assistant", avatar=assistant_avatar):
                    st.markdown(message["content"])


    # --- Sidebar ---

    st.sidebar.title("BOB A.I.")
    with st.sidebar:
        st.button("+New Chat", key="new_chat_button", on_click=new_chat) #button to start a new chat

        #delete current chat button
        if st.button("🗑️ Delete Current Chat", key="delete_current_chat_button"):
            delete_chat(st.session_state.current_chat)

        #selectbox/dropdown/accordion
        #the list holding the chat names is CHAT_NAMES, but this uses a local reference
        chatHistorySelectBox = st.selectbox(
            "View Chat History",
            st.session_state['CHAT_NAMES'],
            index = st.session_state.selected_chat,
            key='chat_history_selector',
            on_change = lambda: chat_switch(
                st.session_state['CHAT_NAMES'].index(st.session_state.chat_history_selector)
            )
        )

        #update select box variable
        #find the index of the selected chat name
        st.session_state.selected_chat = st.session_state['CHAT_NAMES'].index(chatHistorySelectBox)

        #switch chats if needed
        if(st.session_state.current_chat != st.session_state.selected_chat):
            chat_switch(st.session_state.selected_chat)

        #Voice Controls
        st.session_state.voice_mode = st.toggle("🎙️ Voice Mode (talk to Bob)", value=st.session_state.voice_mode)
        st.session_state.auto_speak = st.toggle("🔊 Bob speaks responses", value=st.session_state.auto_speak)

        # --- Rename current chat ---
        current_name = st.session_state['CHAT_NAMES'][st.session_state.current_chat]
        new_name = st.text_input(
            "Rename current chat",
            value=current_name,
            key="rename_current_chat_input"
        )

        if st.button("Save name", key="save_chat_name_button"):
            # Only update if it's not empty and actually changed
            if new_name.strip() and new_name != current_name:
                st.session_state['CHAT_NAMES'][st.session_state.current_chat] = new_name
                st.rerun()


    # --- File Uploading ---

        files_uploaded = st.file_uploader("Pick a file", accept_multiple_files=True) #allows user to upload a file

        #if there are 1 or more files uploaded
        while files_uploaded is not None and len(files_uploaded) > 0:
            i = 0 #counter for files uploaded, used for naming and saving files
            for files in files_uploaded:
                save_folder = 'files_uploaded_to_Bob'  #define the folder to save uploaded files
                if not os.path.exists(save_folder):
                    os.makedirs(save_folder) #if the folder doesn't exist, make it

                #define the full path of the file and the folder
                file_path = os.path.join(save_folder, files_uploaded[i].name)

                #write the information of the file to the folder
                with open(file_path, "wb") as f:
                    f.write(files_uploaded[i].getbuffer())

                st.write(f"Saved: {files_uploaded[i].name}")
                



                #with the file now uploaded and saved, use docling to interpret it
                source = file_path #where the file is coming from
                converter = DocumentConverter() #converter
                doc = converter.convert(source).document #convert the file into a docling document

                #define the full path of the file and the folder
                docling_file_path = os.path.join(save_folder, "docling_" + files_uploaded[i].name)

                #write the information of the file to the folder
                with open(docling_file_path, "wb") as f:
                    f.write((doc.export_to_markdown().encode('utf-8')))

                st.write(f"Saved: {files_uploaded[i].name}")


                #open the file path to read and tell Bob. --> might move this to a later area, so he only reads once..?
                with open(docling_file_path, "r") as f:
                    st.session_state.messages.append(
                            {
                                'role': 'system',
                                'content': f"A file has been uploaded named: {f.name} "                                        
                                            f"The contents of the file is: {f.read()}"
                            }


                    ) #tell the assistant what the file is, but do not print this out

                if len(files_uploaded) > 1:
                    files_uploaded[i]=files_uploaded[i+1]  #move to the next file in the list if there are multiple files uploaded
                    len(files_uploaded) - 1 #decrease the length of the file uploader list by 1 since we have already uploaded one file
                
                else:
                    files_uploaded = None #set the file uploader to None to reset it

                print("File was uploaded btw: " + f.name) #print the name of the file that was uploaded to the terminal for testing purposes



                #i += 1 #iterate the file counter for the next file if there are multiple files uploaded

















        #########
        #file reading space
        #########









    # --- Main Chat Logic ---

# --- Main Chat Logic ---
@st.cache_resource
def get_whisper_model():
    return WhisperModel("base", device="cpu", compute_type="int8")

def transcribe_audio_to_text(wav_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(wav_bytes)
        tmp_path = tmp.name

    whisper_model = get_whisper_model()
    segments, _info = whisper_model.transcribe(tmp_path, vad_filter=True)
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return text

def generate_response_stream():
    response = ollama.chat(
        model=MODEL,
        stream=True,
        messages=st.session_state.messages,
        keep_alive="24h",
        options={"num_predict": 256},
    )

    for chunk in response:
        yield chunk["message"]["content"]

def run_chat_turn(user_text: str):

    st.session_state.messages.append({"role": "user", "content": user_text})


    with unique_message("user"):
        with st.chat_message("user", avatar=user_avatar):
            st.markdown(user_text)


    try:
        with st.chat_message("assistant", avatar=assistant_avatar):
            ensure_tts_worker_running()

            text_placeholder = st.empty()
            full = ""
            speak_buffer = ""
            
            response = ollama.chat(
                model=MODEL,
                stream=True,
                messages=st.session_state.messages,
                keep_alive="24h",
                options={"num_predict": 256},
            )

        for chunk in response:
            token = chunk["message"]["content"]
            full += token
            speak_buffer += token
            text_placeholder.markdown(full)
            
            if st.session_state.auto_speak:
                parts = re.split(r'([.!?]+)', speak_buffer)
                if len(parts) > 3:
                    completed = ""
                    for i in range(0, len(parts)-2, 2):
                        completed += (parts[i] + parts[i+1])
                        
                    enqueue_tts(completed)
                    speak_buffer = parts[-2] + parts[-1]
        assistant_text = full 

        st.session_state.messages.append({"role": "assistant", "content": assistant_text})

        if st.session_state.voice_mode:
            st.session_state.mic_cycle += 1
            st.rerun()

    except Exception:
        st.error("Attempting to start Ollama . . . Please wait a few seconds and then try again.")
        os.system("ollama serve")
        if os.system("pgrep ollama") != 0:
            st.error("Error connecting to Ollama. Ensure Ollama is installed and llava:7b is downloaded.")
            st.stop()
        else:
            st.success("Ollama started successfully! Try again.")
            st.stop()

# --- Voice Input UI ---
if st.session_state.voice_mode:
    st.caption("🎙️ Voice Mode is ON — record a message and Bob will respond.")
    audio = mic_recorder(
        start_prompt="🎙️ Hold to talk",
        stop_prompt="⏹️ Release to send",
        just_once=True,
        key=f"mic_recorder_main_{st.session_state.mic_cycle}",
    )

    if audio and isinstance(audio, dict) and audio.get("bytes"):
        with st.spinner("Transcribing..."):
            spoken_text = transcribe_audio_to_text(audio["bytes"])

        if spoken_text:
            run_chat_turn(spoken_text)
        else:
            st.warning("I couldn't hear anything clearly—try again a bit louder.")

# --- text input only ---
prompt = st.chat_input("Type here", key="chat_input_styled")
if prompt:
    run_chat_turn(prompt)
