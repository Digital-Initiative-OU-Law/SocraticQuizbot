import streamlit as st
# Set page config before any other Streamlit commands
st.set_page_config(page_title="QuizBot", layout="wide")

import os
from datetime import datetime
from dotenv import load_dotenv
from database.models import init_db, get_db_connection
from database.operations import DatabaseOperations
from database.analytics import AnalyticsOperations
from services.openai_service import OpenAIService
from services.pdf_service import PDFService
from services.settings import USE_PGVECTOR, OPENAI_MODEL, OLLAMA_MODEL
from services.retrieval import upsert_document, index_text, search_similar
from utils.auth import Auth

# Load environment variables
load_dotenv()

# Initialize services
openai_service = OpenAIService()
pdf_service = PDFService()
db_ops = DatabaseOperations()

# Initialize database
init_db()

# Session state initialization
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'user_name' not in st.session_state:
    st.session_state.user_name = None
if 'conversation_id' not in st.session_state:
    st.session_state.conversation_id = None
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'quiz_started' not in st.session_state:
    st.session_state.quiz_started = False
if 'show_transcript' not in st.session_state:
    st.session_state.show_transcript = False
if 'custom_openai_key' not in st.session_state:
    st.session_state.custom_openai_key = None
if 'show_conversations' not in st.session_state:
    st.session_state.show_conversations = True

# Load custom CSS
with open('assets/style.css') as f:
    st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

def start_new_quiz():
    if not st.session_state.user_id:
        st.error("Please log in to start a quiz.")
        return False

    try:
        with st.spinner("Processing PDF documents..."):
            # Get summaries instead of raw text
            summaries = pdf_service.extract_summaries('Readings')
            if not summaries:
                st.error("No summaries could be generated from PDFs in the Readings folder.")
                return False
            
            # Combine summaries with separators
            combined_summaries = "\n\n".join([f"=== {filename} ===\n{summary}" 
                                            for filename, summary in summaries.items()])
            
            # Create conversation with meaningful title
            title = openai_service.generate_title_summary(combined_summaries) or f"Quiz {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
            # Infer course/week if a single pair exists in Readings/<course>/<week>/
            base = 'Readings'
            courses = set()
            weeks = set()
            for root, _, files in os.walk(base):
                for f in files:
                    if f.lower().endswith('.pdf'):
                        rel = os.path.relpath(root, base)
                        parts = rel.split(os.sep)
                        if len(parts) >= 2:
                            courses.add(parts[0])
                            weeks.add(parts[1])
            course_val = list(courses)[0] if len(courses) == 1 else None
            week_val = list(weeks)[0] if len(weeks) == 1 else None

            # Backend/model provenance
            model_backend = 'ollama' if os.getenv('USE_OLLAMA', 'false').lower() == 'true' else 'openai'
            model_name = OLLAMA_MODEL if model_backend == 'ollama' else OPENAI_MODEL

            # Create conversation and store summaries as context and metadata
            st.session_state.conversation_id = db_ops.create_conversation(
                st.session_state.user_id,
                title=title,
                context=combined_summaries,
                course=course_val,
                week=week_val,
                model_backend=model_backend,
                model_name=model_name,
                prompt_template_version='v1'
            )

            # Optional: index documents for retrieval if enabled
            if USE_PGVECTOR:
                try:
                    base_dir = 'Readings'
                    for root, _, files in os.walk(base_dir):
                        for f in files:
                            if f.lower().endswith('.pdf'):
                                path = os.path.join(root, f)
                                # derive course/week
                                rel = os.path.relpath(root, base_dir)
                                parts = rel.split(os.sep)
                                course = parts[0] if len(parts) > 1 else None
                                week = parts[1] if len(parts) > 1 else None
                                md5 = pdf_service._calculate_file_hash(path)
                                upsert_document(course, week, f, md5)
                                text = pdf_service._extract_text_with_fallback(path)
                                # Use per-user key if available for embeddings
                                api_key = getattr(st.session_state, 'custom_openai_key', None)
                                provider = 'openai' if model_backend == 'openai' else 'ollama'
                                index_text(md5, text, provider=provider, api_key=api_key)
                except Exception as e:
                    st.info(f"Retrieval indexing skipped: {str(e)}")
            
            # Select a random concept from the summaries for the initial question
            all_concepts = []
            for summary in summaries.values():
                # Split summary into concepts (assuming they're separated by newlines)
                concepts = [c.strip() for c in summary.split('\n') if c.strip()]
                all_concepts.extend(concepts)
            
            if not all_concepts:
                st.error("No concepts found in the summaries.")
                return False
            
            # Choose a random concept
            import random
            initial_concept = random.choice(all_concepts)
            
            # Generate first question based on the chosen concept
            initial_prompt = f"Based on this concept: {initial_concept}, generate an engaging Socratic question to start our discussion."
            # Add retrieval context if available
            retrieved = []
            if USE_PGVECTOR:
                try:
                    # Collect md5s of available documents
                    md5s = []
                    for root, _, files in os.walk('Readings'):
                        for f in files:
                            if f.lower().endswith('.pdf'):
                                md5s.append(pdf_service._calculate_file_hash(os.path.join(root, f)))
                    if md5s:
                        retrieved = [c for c, _ in search_similar(md5s, initial_prompt)][:3]
                except Exception:
                    retrieved = []
            extra_context = ("\n\nRetrieved context:\n" + "\n---\n".join(retrieved)) if retrieved else ""
            response = openai_service.generate_response(initial_prompt, combined_summaries + extra_context)
            
            if response:
                # Save the assistant's first question
                db_ops.save_message(st.session_state.conversation_id, "assistant", response)
                st.session_state.messages = [("assistant", response)]
                st.session_state.quiz_started = True
                st.session_state.show_conversations = False
                
                # Update analytics
                AnalyticsOperations.update_conversation_analytics(st.session_state.conversation_id)
                AnalyticsOperations.update_user_analytics(st.session_state.user_id)
                st.rerun()
                return True
            else:
                st.error("Failed to generate initial question. Please try again.")
                return False
                
    except Exception as e:
        st.error(f"Error starting quiz: {str(e)}")
        return False

def continue_conversation(conv_id):
    """Continue an existing conversation"""
    try:
        if st.session_state.user_id:
            # Verify conversation belongs to user
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM conversations WHERE id = %s AND user_id = %s",
                (conv_id, st.session_state.user_id)
            )
            if not cur.fetchone():
                st.error("Conversation not found.")
                return
            
            # Set conversation state
            st.session_state.conversation_id = conv_id
            messages = db_ops.get_conversation_messages(conv_id)
            st.session_state.messages = [(msg[0], msg[1]) for msg in messages]
            st.session_state.quiz_started = True
            st.session_state.show_conversations = False
            
            cur.close()
            conn.close()
            st.rerun()
            
    except Exception as e:
        st.error(f"Error continuing conversation: {str(e)}")

def main():
    # Authentication
    if not st.session_state.user_id:
        tab1, tab2 = st.tabs(["Login", "Register"])
        
        with tab1:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Login")
                
                if submit:
                    success, user_id, first_name, last_name, api_key = Auth.verify_user(username, password)
                    if success:
                        st.session_state.user_id = user_id
                        st.session_state.user_name = f"{first_name or ''} {last_name or ''}".strip() or username
                        if api_key:
                            st.session_state.custom_openai_key = api_key
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
        
        with tab2:
            with st.form("register_form"):
                llm_choice = st.selectbox(
                    "Choose Language Model",
                    ["OpenAI", "Ollama"],
                    help="Select which language model to use. OpenAI requires an API key, Ollama runs locally."
                )
                
                api_key = st.text_input(
                    "OpenAI API Key",
                    type="password",
                    help="Your personal OpenAI API key (required if using OpenAI)",
                    disabled=llm_choice == "Ollama"
                )
                new_username = st.text_input("Choose Username")
                new_password = st.text_input("Choose Password", type="password")
                first_name = st.text_input("First Name")
                last_name = st.text_input("Last Name")
                
                submit = st.form_submit_button("Register")
                
                if submit:
                    if llm_choice == "OpenAI" and not api_key:
                        st.error("OpenAI API key is required when using OpenAI.")
                        return
                        
                    if llm_choice == "OpenAI" and not openai_service.verify_api_key(api_key):
                        st.error("Invalid OpenAI API key. Please check and try again.")
                        return
                    
                    # Only store API key if using OpenAI
                    store_key = api_key if llm_choice == "OpenAI" else None
                    
                    if Auth.register_user(new_username, new_password, first_name, last_name, store_key):
                        # Set the USE_OLLAMA environment variable based on choice
                        if llm_choice == "Ollama":
                            os.environ['USE_OLLAMA'] = 'true'
                        st.success("Registration successful! Please login.")
                    else:
                        st.error("Registration failed. Username might be taken.")
        return

    # Add API key management in sidebar
    with st.sidebar:
        with st.expander("Settings", expanded=False):
            # LLM Choice
            current_llm = "Ollama" if os.getenv('USE_OLLAMA', 'false').lower() == 'true' else "OpenAI"
            new_llm = st.selectbox(
                "Language Model",
                ["OpenAI", "Ollama"],
                index=0 if current_llm == "OpenAI" else 1,
                help="Select which language model to use"
            )
            
            # Only show API key settings if using OpenAI
            if new_llm == "OpenAI":
                st.info("Your OpenAI API key is required to use OpenAI's models")
                current_key = "•" * 8 if st.session_state.custom_openai_key else "No key set (using system default)"
                st.text(f"Current API Key: {current_key}")
                
                new_api_key = st.text_input(
                    "Update OpenAI API Key",
                    type="password",
                    help="Enter your OpenAI API key to use your own account."
                )
                if st.button("Update Settings"):
                    if new_api_key:
                        if openai_service.verify_api_key(new_api_key):
                            if Auth.update_api_key(st.session_state.user_id, new_api_key):
                                st.session_state.custom_openai_key = new_api_key
                                os.environ['USE_OLLAMA'] = 'false'
                                st.success("Settings updated successfully!")
                                st.rerun()
                            else:
                                st.error("Failed to update settings.")
                        else:
                            st.error("Invalid API key. Please check and try again.")
                    else:
                        # Remove custom API key
                        if Auth.update_api_key(st.session_state.user_id, None):
                            st.session_state.custom_openai_key = None
                            st.success("Switched to system default API key.")
                            st.rerun()
                        else:
                            st.error("Failed to update settings.")
            else:  # Ollama selected
                if st.button("Update Settings"):
                    os.environ['USE_OLLAMA'] = 'true'
                    st.success("Switched to Ollama!")
                    st.rerun()

    # Main content area
    if st.session_state.quiz_started and not st.session_state.show_conversations:
        st.title("Current Quiz")
        
        # Back to conversations button
        col1, col2 = st.columns([6, 1])
        with col2:
            if st.button("⬅️ Back", key="back_to_conversations"):
                st.session_state.quiz_started = False
                st.session_state.show_conversations = True
                st.rerun()
        
        # Display chat messages
        for role, content in st.session_state.messages:
            with st.chat_message(role):
                st.write(content)
        
        # Chat input and End Quiz button in columns
        col1, col2 = st.columns([4, 1])
        with col1:
            if prompt := st.chat_input("Type your response..."):
                # Save user message
                message_id = db_ops.save_message(st.session_state.conversation_id, "user", prompt)
                st.session_state.messages.append(("user", prompt))

                # Prepare context (with optional retrieval augmentation)
                context = db_ops.get_conversation_context(st.session_state.conversation_id)
                extra_context = ""
                if USE_PGVECTOR:
                    try:
                        md5s = []
                        for root, _, files in os.walk('Readings'):
                            for f in files:
                                if f.lower().endswith('.pdf'):
                                    md5s.append(pdf_service._calculate_file_hash(os.path.join(root, f)))
                        if md5s:
                            sims = search_similar(md5s, prompt)
                            if sims:
                                extra_context = "\n\nRetrieved context:\n" + "\n---\n".join([c for c, _ in sims[:3]])
                    except Exception:
                        extra_context = ""

                # Stream assistant response (OpenAI) or fallback to full
                final_text = ""
                with st.chat_message("assistant"):
                    placeholder = st.empty()
                    for chunk in openai_service.stream_response(prompt, context + extra_context):
                        final_text += chunk
                        placeholder.markdown(final_text)

                if final_text:
                    db_ops.save_message(st.session_state.conversation_id, "assistant", final_text)
                    st.session_state.messages.append(("assistant", final_text))

                # Update analytics
                AnalyticsOperations.update_message_analytics(message_id)
                AnalyticsOperations.update_conversation_analytics(st.session_state.conversation_id)
                AnalyticsOperations.update_user_analytics(st.session_state.user_id)

        with col2:
            if st.button("End Quiz", type="primary"):
                # Get conversation messages
                messages = db_ops.get_conversation_messages(st.session_state.conversation_id)
                # Format transcript
                transcript = db_ops.format_transcript(messages)
                # End the conversation in database
                db_ops.end_conversation(st.session_state.conversation_id)
                # Offer transcript download
                st.download_button(
                    "Download Transcript",
                    transcript,
                    file_name=f"quiz_transcript_{st.session_state.conversation_id}.txt",
                    mime="text/plain"
                )
                # Reset session state
                st.session_state.quiz_started = False
                st.session_state.show_conversations = True
                st.rerun()
    else:
        # Main interface
        col1, col2 = st.columns([3, 1])
        with col1:
            st.title("QuizBot")
        with col2:
            if st.button("Start New Quiz", type="primary", key="start_quiz", use_container_width=True):
                start_new_quiz()

        st.markdown("---")
        st.subheader("Your Conversations")
        
        # Show conversations
        conversations = db_ops.get_user_conversations(st.session_state.user_id)
        if conversations:
            for conv in conversations:
                conv_id, title, context, start_time, end_time, status, msg_count, last_activity = conv
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.write(f"**{title}**")
                        st.write(f"Messages: {msg_count} | Status: {status.title()}")
                    with col2:
                        if status == 'ongoing':
                            if st.button("▶️ Continue", key=f"continue_{conv_id}"):
                                continue_conversation(conv_id)
                    with col3:
                        if st.button("📋 View", key=f"view_{conv_id}"):
                            continue_conversation(conv_id)
                st.markdown("---")
        else:
            st.info("Start a new quiz to begin learning!")

if __name__ == "__main__":
    main()
