import os
import requests
import json
import streamlit as st
from functools import lru_cache
import tiktoken

class OllamaService:
    def __init__(self):
        self.host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        self.model = os.getenv('OLLAMA_MODEL', 'mistral')
        self.max_retries = 3
        self.timeout = 30
        self.cache_ttl = 3600
        
    def generate_response(self, prompt: str, context: str = "") -> str:
        """Generate a response using Ollama"""
        try:
            # Prepare the messages with conversation history
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
            
            # Make request to Ollama
            response = requests.post(
                f"{self.host}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 500,
                    }
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['message']['content'].strip()
            else:
                st.error(f"Error from Ollama API: {response.text}")
                return None
                
        except Exception as e:
            st.error(f"Error generating response: {str(e)}")
            return None
            
    def generate_title_summary(self, text: str) -> str:
        """Generate a title summary for a conversation"""
        try:
            prompt = f"Based on the following text, generate a brief (3-5 words) title that captures the main topic:\n\n{text[:1000]}..."
            
            response = requests.post(
                f"{self.host}/api/chat",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 50,
                    }
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['message']['content'].strip()
            return None
            
        except Exception as e:
            print(f"Error generating title: {str(e)}")
            return None
            
    def generate_summary(self, text: str) -> str:
        """Generate a summary using Ollama"""
        try:
            response = requests.post(
                f"{self.host}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "Create a concise summary of key concepts from the provided text. Focus on main ideas and theories that could be used for Socratic questioning."},
                        {"role": "user", "content": text}
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 1000,
                    }
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['message']['content'].strip()
            else:
                st.error(f"Error from Ollama API: {response.text}")
                return None
            
        except Exception as e:
            st.error(f"Error generating summary: {str(e)}")
            return None
            
    @lru_cache(maxsize=100)
    def count_tokens(self, text: str) -> int:
        """Estimate token count - using tiktoken for consistency"""
        try:
            encoding = tiktoken.encoding_for_model("gpt-4")  # Using GPT-4 encoding as baseline
            return len(encoding.encode(text))
        except Exception:
            # Fallback to simple word count estimation
            return len(text.split()) * 1.3
            
    def verify_connection(self) -> bool:
        """Verify if Ollama is accessible and the model is available"""
        try:
            response = requests.get(f"{self.host}/api/tags")
            if response.status_code == 200:
                models = response.json().get('models', [])
                return any(model['name'] == self.model for model in models)
            return False
        except Exception:
            return False
