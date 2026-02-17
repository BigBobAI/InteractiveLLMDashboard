import os
os.environ["STREAMLIT_DEVELOPMENT_MODE"] = "false"
os.environ["STREAMLIT_DEV_MODE"] = "0"
os.environ["STREAMLIT_WATCHER_TYPE"] = "none"
os.environ["STREAMLIT_SERVER_PORT"] = "8501"
os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
import sys
import config 
import uuid 
import requests
import streamlit as st #in venv --> pip install streamlit
import ollama #in venv --> pip install ollama
from pypdf import PdfReader #in venv --> pip install pypdf
import pandas as pd #in venv --> pip install pandas, pip install tabulate
from docx import Document #in venv --> pip install python-docx

#this comment is being added for test purposes

#also note, for installations you should also be able to do pip install -r requirements.txt (all of the requirements should be in there)

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
    #ben warmup process
    def warmup_model():
        try:
            requests.post(
                "http://localhost:11434/api/chat",
                json={"model": MODEL},
                timeout=30
            )
        except:
            pass


    # --- Session State Initialization---
    #This loads the model and keeps in active state
    if "MODEL_WARMED" not in st.session_state:
        with st.spinner("Loading Big Bob Model"):
            warmup_model()
        st.session_state["MODEL_WARMED"] = True



    if 'CHATS' not in st.session_state:
        #CHATS is a list of chat histories (list of lists of dictionaries)
        st.session_state['CHATS'] = [INITIAL_CHAT_HISTORY.copy()] 
        st.session_state['CHAT_NAMES'] = ["Chat 1"]
        st.session_state.current_chat = 0
        st.session_state.selected_chat = 0

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

    #create delete chat feature
    def delete_chat(target_chat: int): #keep at least 1 chat available not 0
        if len(st.session_state['CHATS']) <= 1:
            return

        st.session_state['CHATS'][st.session_state.current_chat] = st.session_state.messages

        st.session_state['CHATS'].pop(target_chat)
        st.session_state['CHAT_NAMES'].pop(target_chat)

        if target_chat < st.session_state.current_chat:
            st.session_state.current_chat -= 1

        elif target_chat == st.session_state.current_chat:
            st.session_state.current_chat = max(0, st.session_state.current_chat - 1)

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

        files_uploaded = st.file_uploader("Pick a file") #allows user to upload a file

        if files_uploaded is not None: #if there is a file that have been uploaded

            print(f"A file has been uploaded. Name: '{files_uploaded.name}', Type: '{files_uploaded.type}'") #this is a test to print to the console. delete later

            if files_uploaded.type == 'text/plain': #if the file i sjust plain text
                file_contents = files_uploaded.read().decode("utf-8") #read and decode the file (put that in file data)
                st.session_state.messages.append(
                    {
                        'role': 'system',
                        'content': f"A file has been uploaded named: {files_uploaded.name} "
                                   f"The contents of the file is: {file_contents}"
                    }
                ) #tell the assistant what the file is, but do not print this out
            
            elif files_uploaded.type == 'application/pdf': #if the file is a pdf
                file_contents = PdfReader(files_uploaded) #read and decode the file (put that in file data)
                number_of_pages = len(file_contents.pages) #find the number of pages
                #decode each page and print each page individually to the assistant
                for i in range(number_of_pages): 
                    page = file_contents.pages[i] 
                    file_text = page.extract_text()
                    #system message for LLM (append for each page)
                    st.session_state.messages.append(
                        {
                            'role': 'system',
                            'content': (
                                f"A file has been uploaded named: {files_uploaded.name} \n"
                                f"The contents of page {i+1} the file is: {file_text} \n"
                                f"The file is {number_of_pages} pages long."
                            )
                        }
                    ) #tell the assistant what the file is, but do not print this out

            elif files_uploaded.type == 'text/csv': #if it's a csv file
                df = pd.read_csv(files_uploaded)
                file_contents = df.to_markdown(index = False)

                #system message for LLM
                st.session_state.messages.append(
                    {
                        'role' : 'system',
                        'content' : f"A file has been uploaded named: {files_uploaded.name} \n"
                                    f"The contents of the CSV  file are: \n {file_contents}"
                    }
                )

            elif files_uploaded.type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document': #if it's a .docx file

                document = Document(files_uploaded)
                file_contents = ""
                for paragraph in document.paragraphs:
                    file_contents += paragraph.text + "\n"

                #system message for LLM
                st.session_state.messages.append(
                    {
                        'role': 'system',
                        'content': f"A file has been uploaded named: {files_uploaded.name} \n"
                                    f"The contents of the Word document are: \n{file_contents}"
                    }
                )

            else:
                print("There's an issue with finding the file type dawg")
                st.session_state.messages.append(
                    {
                        'role': 'assistant',
                        'content': "There's an issue trying to read this type of file. Please let devlopers know so that I can be improved to support this need."
                    }
                ) #tell the assistant what the file is, but do not print this out

        st.button("-Clear All Chats", key="clear_chat_button", on_click=clear_all_chats) #button to clear all chats

        delete_disabled = (len(st.session_state['CHATS']) <= 1)

        if st.button("Delete Selected Chat", key="delete_selected_chat_button", disabled=delete_disabled): #delete current selected chat
            delete_chat(st.session_state.selected_chat)
    # --- Main Chat Logic ---

    def generate_response():
        #only pass non-system messages (or the last few if context is long) 
        #for simplicity, we pass all messages including the hidden system prompt for now
    
        response = ollama.chat(model=MODEL, stream=True, messages=st.session_state.messages) #will get the response from the model

        keep_alive="24h",
        options={
            "num_predict": 256
        }

        st.session_state["full_message"] = "" #reset full message before generation
        for chunk in response:
            token = chunk["message"]["content"] #token is getting the chunk content 
            st.session_state["full_message"] += token #adds to the full message so far
            yield token #display the token





    if prompt := st.chat_input("Type here", key="chat_input_styled"): #this text will show up in the input bar
        st.session_state.messages.append({"role": "user", "content": prompt}) #if the user types a prompt append it
        
        #display the user prompt
        with unique_message("user"):
            with st.chat_message("user", avatar=user_avatar):
                st.markdown(prompt) 
        

        try:
            #generate and display the assistant response
            with st.chat_message("assistant", avatar=assistant_avatar):
                stream = generate_response()
                response = st.write_stream(stream) #write the stream response
                st.session_state.messages.append({'role': 'assistant', 'content': response}) #append assitant response into content
        except Exception as e: #if ollama isn't running, there will be an error, attempt to run ollama, if that fails, provide instructions for how to get ollama
            st.error("Attempting to start Ollama . . . Please wait a few seconds and then try your prompt again.")
            os.system("ollama serve")
            if os.system("pgrep ollama") != 0:
                st.error("It appears there was an error connecting to the Ollama model. Please ensure that Ollama is installed and the model llava:7b is downloaded. ")
                st.error("If Ollama is already installed, please try to manualy run it by entering the command 'ollama serve' in your terminal, and then rerun or reload Bob.")
                st.error("To install Ollama: visit https://ollama.com/ and download.")
                st.error("Once ollama is installed, run the command 'ollama run llava:7b' in your terminal to download the model.")
                st.error( "Please consult the setup documentation for further details.")
            else:
                st.error("Ollama has started successfully! Feel free to continue our conversation now!") #if ollama actually does run, it technically shouldn't reach here.... but just in case
            st.stop()
            