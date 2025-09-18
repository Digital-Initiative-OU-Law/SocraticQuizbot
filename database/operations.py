from .models import get_db_connection
from datetime import datetime

class DatabaseOperations:
    @staticmethod
    def save_message(conversation_id: int, role: str, content: str):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (%s, %s, %s) RETURNING id",
            (conversation_id, role, content)
        )
        message_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return message_id

    @staticmethod
    def create_conversation(user_id: int, title: str = None, context: str = None,
                            course: str = None, week: str = None,
                            model_backend: str = None, model_name: str = None,
                            prompt_template_version: str = None) -> int:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Generate default title if none provided
        if not title:
            title = f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
        cur.execute(
            """INSERT INTO conversations (user_id, title, context, course, week, model_backend, model_name, prompt_template_version) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (user_id, title, context, course, week, model_backend, model_name, prompt_template_version)
        )
        conversation_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        return conversation_id

    @staticmethod
    def get_user_conversations(user_id: int):
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                c.id,
                COALESCE(c.title, 'Conversation ' || to_char(c.start_time, 'YYYY-MM-DD HH24:MI')) as title,
                COALESCE(c.context, '') as context,
                c.start_time,
                c.end_time,
                c.completion_status,
                COUNT(m.id) as message_count,
                MAX(m.timestamp) as last_activity
            FROM conversations c
            LEFT JOIN messages m ON c.id = m.conversation_id
            WHERE c.user_id = %s
            GROUP BY c.id, c.title, c.context, c.start_time, c.end_time, c.completion_status
            ORDER BY 
                CASE WHEN c.completion_status = 'ongoing' THEN 0 ELSE 1 END,
                last_activity DESC NULLS LAST
        """, (user_id,))
        
        conversations = cur.fetchall()
        cur.close()
        conn.close()
        return conversations

    @staticmethod
    def get_conversation_context(conversation_id: int) -> str:
        """Get the context of a conversation"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            "SELECT context FROM conversations WHERE id = %s",
            (conversation_id,)
        )
        result = cur.fetchone()
        
        cur.close()
        conn.close()
        
        return result[0] if result else ""

    @staticmethod
    def update_conversation(conversation_id: int, title: str = None, context: str = None):
        conn = get_db_connection()
        cur = conn.cursor()
        
        update_fields = []
        params = []
        
        if title is not None:
            update_fields.append("title = %s")
            params.append(title)
        if context is not None:
            update_fields.append("context = %s")
            params.append(context)
        
        if not update_fields:
            cur.close()
            conn.close()
            return
        
        query = f"""
            UPDATE conversations 
            SET {', '.join(update_fields)}
            WHERE id = %s
        """
        params.append(conversation_id)
        cur.execute(query, params)
        conn.commit()
        
        cur.close()
        conn.close()

    @staticmethod
    def end_conversation(conversation_id: int):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE conversations SET end_time = %s, completion_status = 'completed' WHERE id = %s",
            (datetime.now(), conversation_id)
        )
        conn.commit()
        cur.close()
        conn.close()

    @staticmethod
    def get_conversation_messages(conversation_id: int):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT m.role, m.content, m.timestamp, 
                   c.start_time, c.end_time,
                   u.first_name, u.last_name
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            JOIN users u ON c.user_id = u.id
            WHERE m.conversation_id = %s 
            ORDER BY m.timestamp""",
            (conversation_id,)
        )
        messages = cur.fetchall()
        cur.close()
        conn.close()
        return messages

    @staticmethod
    def format_transcript(messages) -> str:
        if not messages:
            return "No messages found in conversation."
        
        # Get conversation details and user info from the first message
        _, _, _, start_time, end_time, first_name, last_name = messages[0]
        user_full_name = f"{first_name} {last_name}".strip() or "Anonymous User"
        
        # Format header
        transcript = [
            "=== QuizBot Conversation Transcript ===",
            f"Student: {user_full_name}",
            f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"{'Ended: ' + end_time.strftime('%Y-%m-%d %H:%M:%S') if end_time else 'Status: Ongoing'}",
            "=" * 50,
            ""
        ]
        
        # Format messages
        for role, content, timestamp, *_ in messages:
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            speaker = "QuizBot" if role == "assistant" else user_full_name
            transcript.extend([
                f"[{timestamp_str}] {speaker}:",
                f"{content}",
                "-" * 40,
                ""
            ])
        
        return "\n".join(transcript)
