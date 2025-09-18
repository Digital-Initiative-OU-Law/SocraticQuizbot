import streamlit as st
import hashlib
from database.models import get_db_connection
from services.openai_service import OpenAIService
from services.crypto import CryptoService

class Auth:
    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    def verify_user(username: str, password: str) -> tuple:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            """SELECT id, password_hash, first_name, last_name, role, openai_api_key, openai_api_key_enc
               FROM users WHERE username = %s""",
            (username,)
        )
        result = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if result and result[1] == Auth.hash_password(password):
            # If user has a custom API key, decrypt preferred enc column or fallback to plaintext
            api_key_plain = result[5]
            api_key_enc = result[6]
            crypto = CryptoService()
            decrypted = crypto.decrypt(api_key_enc) if api_key_enc else None
            effective_key = decrypted or api_key_plain
            if effective_key:
                st.session_state.custom_openai_key = effective_key
            return True, result[0], result[2], result[3], effective_key
        return False, None, None, None, None

    @staticmethod
    def is_instructor(user_id: int) -> bool:
        """Check if a user has instructor role"""
        if not user_id:
            return False
            
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        result = cur.fetchone()
        
        cur.close()
        conn.close()
        
        return result and result[0] == 'instructor'

    @staticmethod
    def register_user(username: str, password: str, first_name: str, last_name: str, openai_api_key: str = None) -> bool:
        # Verify API key before registration
        if openai_api_key and not OpenAIService().verify_api_key(openai_api_key):
            st.error("Invalid OpenAI API key provided.")
            return False

        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Check if username already exists
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cur.fetchone():
                st.error("Username already taken.")
                return False
            
            # Encrypt key if crypto is enabled; store in enc column, else plaintext
            crypto = CryptoService()
            enc_blob = crypto.encrypt(openai_api_key) if openai_api_key else None
            plaintext_key = None if enc_blob else openai_api_key

            cur.execute(
                """INSERT INTO users (username, password_hash, first_name, last_name, role, openai_api_key, openai_api_key_enc) 
                   VALUES (%s, %s, %s, %s, 'student', %s, %s)""",
                (username, Auth.hash_password(password), first_name, last_name, plaintext_key, enc_blob)
            )
            
            conn.commit()
            cur.close()
            conn.close()
            return True
        except Exception as e:
            st.error(f"Registration failed: {str(e)}")
            return False

    @staticmethod
    def update_api_key(user_id: int, api_key: str = None) -> bool:
        try:
            # Verify new API key if provided
            if api_key and not OpenAIService().verify_api_key(api_key):
                st.error("Invalid OpenAI API key provided.")
                return False

            conn = get_db_connection()
            cur = conn.cursor()
            
            crypto = CryptoService()
            enc_blob = crypto.encrypt(api_key) if api_key else None
            plaintext_key = None if enc_blob else api_key

            cur.execute(
                "UPDATE users SET openai_api_key = %s, openai_api_key_enc = %s WHERE id = %s",
                (plaintext_key, enc_blob, user_id)
            )
            
            conn.commit()
            cur.close()
            conn.close()
            
            # Update session state
            st.session_state.custom_openai_key = api_key
            return True
        except Exception as e:
            st.error(f"Failed to update API key: {str(e)}")
            return False
