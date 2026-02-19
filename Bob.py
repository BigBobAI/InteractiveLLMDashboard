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


    #start off with an uploader key for the file uploader in the session state (this is important to be able to clear out file uploader)
    if "uploader_key" not in st.session_state:
        st.session_state["uploader_key"] = 0

    #this clears the file loader
    def clear_file_uploader():
        st.session_state["uploader_key"] += 1 #increment the uploader key to reset the file uploader

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

    def delete_chat(chat_index: int): #delete single chat function 
        if len(st.session_state['CHATS']) <= 1: #dont allow deleting last chat
            st.warning("You are not allowed to delete tthe remaining chat.")
            return
        
        st.session_state['CHATS'].pop(chat_index) #remove the chat + its name
        st.session_state['CHAT_NAMES'].pop(chat_index)

        if chat_index < st.session_state.current_chat: #if we deleted a chat before current, shift current_chat left
            st.session_state.current_chat -= 1

        if chat_index == st.session_state.current_chat: #deleted current chat, pick valid replacement
            if st.session_state.current_chat >= len(st.session_state['CHATS']): #pop, current_chat points to next item
                st.session_state.current_chat = len(st.session_state['CHATS']) - 1

        st.session_state.selected_chat = st.session_state.current_chat #selected chat matches the current chat check

        st.session_state.messages = st.session_state['CHATS'][st.session_state.current_chat].copy() #load the messages from now-current chat
        st.rerun()


    def make_unique_chat_name(desired_name: str, current_chat_index: int) -> str: #function makes it so when you have a chat with same name it increments it
        base = desired_name.strip() ##returns unique chat name. If desired_name exists then (case-insensitive) appends -1, -2.
        if not base:
            return ""
        
        existing_names = [
            n for i, n in enumerate(st.session_state['CHAT_NAMES'])
            if i != current_chat_index
        ]
        #compare its case-insensitively 
        existing_lower = {n.lower() for n in existing_names}

        if base.lower() not in existing_lower:
            return base
        
        suffix = 1
        while f"{base}-{suffix}".lower() in existing_lower:
            suffix += 1

        return f"{base}-{suffix}"


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

        #Chat Deletion Button
        if st.button("-Delete Current Chat", key="delete_current_chat_button"):
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

        # --- Rename current chat ---
        current_name = st.session_state['CHAT_NAMES'][st.session_state.current_chat]
        new_name = st.text_input(
            "Rename current chat",
            value=current_name,
            key="rename_current_chat_input"
        )

        if st.button("Save name", key="save_chat_name_button"):
            # Only update if it's not empty and actually changed
            desired = new_name.strip()

            if not desired:
                st.warning("Chat name cannot be empty.") #error if name is empt
            else: 
                unique_name = make_unique_chat_name(desired, st.session_state.current_chat)
                
                st.session_state['CHAT_NAMES'][st.session_state.current_chat] = unique_name

                if unique_name != desired:
                    st.info(f"Chat name already exists. Saved as '{unique_name}' instead.")
                else:
                    st.success("Chat renamed successfully.")
                st.rerun()

    # --- File Uploading ---

        files_uploaded = st.file_uploader("Pick a file", accept_multiple_files=True, key=st.session_state["uploader_key"]) #allows user to upload a file

        #if there are 1 or more files uploaded
        if files_uploaded is not None and len(files_uploaded) > 0:
            i = 0 #counter for files uploaded, used for naming and saving files
            files_uploaded_length = len(files_uploaded) #length of the file uploader list, used to determine when we have uploaded all files in the list
            for files in files_uploaded:
                save_folder = 'files_uploaded_to_Bob'  #define the folder to save uploaded files
                if not os.path.exists(save_folder):
                    os.makedirs(save_folder) #if the folder doesn't exist, make it

                #define the full path of the file and the folder
                file_path = os.path.join(save_folder, files_uploaded[i].name)

                #write the information of the file to the folder
                with open(file_path, "wb") as f:
                    f.write(files_uploaded[i].getbuffer())                



                #DOCLING STUFF IS GOING TO HAPPEN BELOW#

                #with the file now uploaded and saved, use docling to interpret it
                source = file_path #where the file is coming from
                converter = DocumentConverter() #converter
                doc = converter.convert(source).document #convert the file into a docling document

                #define the full path of the file and the folder
                docling_file_path = os.path.join(save_folder, "docling_" + files_uploaded[i].name)

                #write the information of the file to the folder
                with open(docling_file_path, "wb") as f:
                    f.write((doc.export_to_markdown().encode('utf-8')))


                #open the file path to read and tell Bob the file name and contents
                with open(docling_file_path, "r") as f:
                    st.session_state.messages.append(
                            {
                                'role': 'system',
                                'content': f"A file has been uploaded named: {f.name} "                                        
                                            f"The contents of the file is: {f.read()}"
                            }
                    ) 
                print("File was uploaded btw: " + f.name) #print the name of the file that was uploaded to the terminal for testing purposes

                files_uploaded_length -= 1 #decrease the length of the file uploader list by 1 since we have already uploaded one file
                if files_uploaded_length >= 1:
                    files_uploaded[i]=files_uploaded[i+1]  #move to the next file in the list if there are multiple files uploaded
                    i += 1 #increment the file uploader list counter to move to the next file in the list
                
                elif files_uploaded_length == 0: #if there are no more files to upload, clear the file uploader and let the user know their files have been processed
                    clear_file_uploader() #all files have been read, so clear the file uploader for *new* files
                    st.session_state.messages.append( #let the user know their files have been processed
                            {
                                'role': 'assistant',
                                'content': "All files have been uploaded and processed. How may I assist you with them?"
                            }
                    )
                    st.rerun() #rerun to update the chat with the new assistant message about files being uploaded and processed


                




















        #########
        #file reading space
        #########









        st.button("-Clear All Chats", key="clear_chat_button", on_click=clear_all_chats) #button to clear all chats

    # --- Main Chat Logic ---

    def generate_response():
        #only pass non-system messages (or the last few if context is long) 
        #for simplicity, we pass all messages including the hidden system prompt for now
    
        response = ollama.chat(model=MODEL, stream=True, messages=st.session_state.messages) #will get the response from the model

        keep_alive="24h", #keep him running!
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
        