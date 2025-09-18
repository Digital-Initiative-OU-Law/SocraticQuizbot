import os
from openai import OpenAI
import time
import streamlit as st
from functools import lru_cache
import tiktoken
import tenacity
from .ollama_service import OllamaService
from services.settings import FEATURE_STREAMING, OPENAI_MODEL

class OpenAIService:
    def __init__(self):
        self.initialize_service()
        
        self.max_retries = 5
        self.timeout = 20
        self.cache_ttl = 3600
        self.encoder = tiktoken.encoding_for_model("gpt-4")
        self.max_history_tokens = 2000

    def initialize_service(self):
        """Initialize or reinitialize the service based on current settings"""
        # Check if we should use Ollama
        self.use_ollama = os.getenv('USE_OLLAMA', 'false').lower() == 'true'
        if self.use_ollama:
            self.ollama = OllamaService()
            if hasattr(self, 'client'):
                del self.client
        else:
            # Priority order for API key:
            # 1. User's custom key from session
            # 2. Environment variable from .env
            # 3. System default (if available)
            self.client = OpenAI(api_key=self._get_api_key())
            if hasattr(self, 'ollama'):
                del self.ollama

    def _get_api_key(self):
        if self.use_ollama:
            return None
            
        # First check session state for user's custom key
        if hasattr(st.session_state, 'custom_openai_key') and st.session_state.custom_openai_key:
            return st.session_state.custom_openai_key
            
        # Then check .env file
        env_key = os.getenv('OPENAI_API_KEY')
        if env_key:
            return env_key
            
        # No key available
        if not self.use_ollama:  # Only show error if we're trying to use OpenAI
            st.error("No OpenAI API key found. Please add your API key in Settings.")
        return None

    def verify_api_key(self, api_key: str) -> bool:
        """Verify if the provided OpenAI API key is valid"""
        if self.use_ollama:
            return self.ollama.verify_connection()
            
        if not api_key:
            return False
            
        try:
            # Create a temporary client with the provided key
            temp_client = OpenAI(api_key=api_key)
            
            # Try a simple API call to verify the key
            temp_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )
            return True
        except Exception as e:
            st.error(f"API key verification failed: {str(e)}")
            return False

    def generate_response(self, prompt: str, context: str) -> str:
        """Generate a response for the quiz dialogue"""
        # Reinitialize service in case settings changed
        self.initialize_service()
        
        if self.use_ollama:
            return self.ollama.generate_response(prompt, context)
            
        try:
            # Get the last few messages to maintain conversation context
            messages = [
                {"role": "system", "content": "You are a Socratic professor engaging in a dialogue with a student. Ask probing questions that encourage critical thinking and deeper analysis. Never explain your reasoning or teaching methodology. Do not provide explanations, commentary, or direct answers. Simply ask thoughtful questions that guide the student to discover insights on their own. Keep questions focused on the current topic and build upon the student's previous responses."},
                {"role": "assistant", "content": f"Context: {context[:2000]}..."}
            ]
            
            # Add conversation history if available
            if hasattr(st.session_state, 'messages') and st.session_state.messages:
                for role, content in st.session_state.messages[-3:]:  # Include last 3 messages
                    messages.append({"role": role, "content": content})
            
            # Add the current prompt
            messages.append({"role": "user", "content": prompt})
            
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                max_tokens=500,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error generating response: {str(e)}")
            return None

    def generate_title_summary(self, text: str) -> str:
        """Generate a title summary for the conversation"""
        # Reinitialize service in case settings changed
        self.initialize_service()
        
        if self.use_ollama:
            return self.ollama.generate_title_summary(text)
            
        try:
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "user", "content": f"Based on the following text, generate a brief (3-5 words) title that captures the main topic:\n\n{text[:1000]}..."}
                ],
                max_tokens=50,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error generating title: {str(e)}")
            return None

    def generate_summary(self, text: str) -> str:
        """Generate a summary of the text content"""
        # Reinitialize service in case settings changed
        self.initialize_service()
        
        if self.use_ollama:
            return self.ollama.generate_summary(text)
        
        try:
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "Create a concise summary of key concepts from the provided text. Focus on main ideas and theories that could be used for Socratic questioning."},
                    {"role": "user", "content": text}
                ],
                max_tokens=1000,
                temperature=0.3
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error generating summary: {str(e)}")
            return None

    def stream_response(self, prompt: str, context: str):
        """Yield tokens for a streamed response (OpenAI only)."""
        self.initialize_service()
        if self.use_ollama or not FEATURE_STREAMING:
            # Fallback: yield a single full response
            full = self.generate_response(prompt, context)
            if full:
                yield full
            return
        try:
            messages = [
                {"role": "system", "content": "You are a Socratic professor engaging in a dialogue with a student. Ask probing questions that encourage critical thinking and deeper analysis. Never explain your reasoning or teaching methodology. Do not provide explanations, commentary, or direct answers. Simply ask thoughtful questions that guide the student to discover insights on their own. Keep questions focused on the current topic and build upon the student's previous responses."},
                {"role": "assistant", "content": f"Context: {context[:2000]}..."}
            ]
            if hasattr(st.session_state, 'messages') and st.session_state.messages:
                for role, content in st.session_state.messages[-3:]:
                    messages.append({"role": role, "content": content})
            messages.append({"role": "user", "content": prompt})

            with self.client.chat.completions.stream(
                model=OPENAI_MODEL,
                messages=messages,
                max_tokens=500,
                temperature=0.7,
            ) as stream:
                for event in stream:
                    if event.type == "chunk":
                        delta = event.choices[0].delta  # type: ignore[attr-defined]
                        if delta and getattr(delta, 'content', None):
                            yield delta.content
                final = stream.get_final_completion()
                if final and final.choices and final.choices[0].message.content:
                    # Ensure the last bit is yielded if needed
                    pass
        except Exception as e:
            print(f"Streaming error: {str(e)}")
