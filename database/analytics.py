import streamlit as st
from datetime import datetime, timedelta
from .models import get_db_connection
import pandas as pd
import numpy as np
import re

class AnalyticsOperations:
    @staticmethod
    def count_sentences(text):
        """Count the number of sentences in a text"""
        if not text:
            return 0
        sentences = re.split(r'[.!?]+', text)
        return len([s for s in sentences if s.strip()])

    @staticmethod
    def update_message_analytics(message_id):
        """Update analytics for a single message"""
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            message_content = None
            
            cur.execute("SELECT content FROM messages WHERE id = %s", (message_id,))
            result = cur.fetchone()
            if result:
                message_content = result[0]
            
            if not message_content:
                return
                
            sentence_count = AnalyticsOperations.count_sentences(message_content)
            word_count = len(message_content.split())
            
            cur.execute("""
                WITH message_metrics AS (
                    SELECT 
                        m.id,
                        m.conversation_id,
                        c.user_id,
                        %s as word_count,
                        NULLIF(EXTRACT(EPOCH FROM (m.timestamp - LAG(m.timestamp) OVER (
                            PARTITION BY m.conversation_id 
                            ORDER BY m.timestamp
                        ))), 0) as response_time
                    FROM messages m
                    JOIN conversations c ON m.conversation_id = c.id
                    WHERE m.id = %s
                )
                UPDATE messages m
                SET 
                    word_count = mm.word_count,
                    response_time = CASE 
                        WHEN mm.response_time > 3600 THEN NULL 
                        ELSE mm.response_time 
                    END,
                    sentence_count = %s
                FROM message_metrics mm
                WHERE m.id = mm.id
                RETURNING mm.conversation_id
            """, (word_count, message_id, sentence_count))
            
            result = cur.fetchone()
            if result:
                conversation_id = result[0]
                
                cur.execute("""
                    UPDATE conversations
                    SET sentence_count = (
                        SELECT COALESCE(SUM(sentence_count), 0)
                        FROM messages
                        WHERE conversation_id = %s
                        AND role = 'user'
                    )
                    WHERE id = %s
                """, (conversation_id, conversation_id))
            
            conn.commit()
        except Exception as e:
            print(f"Error updating message analytics: {str(e)}")
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    @staticmethod
    def update_conversation_analytics(conversation_id):
        """Update analytics for a conversation"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute('''
                UPDATE conversations c
                SET 
                    response_count = (
                        SELECT COUNT(*) 
                        FROM messages 
                        WHERE conversation_id = c.id 
                        AND role = 'user'
                    ),
                    average_response_time = (
                        SELECT COALESCE(AVG(NULLIF(response_time, 0))::float, 0.0)
                        FROM messages 
                        WHERE conversation_id = c.id 
                        AND response_time IS NOT NULL
                    )
                WHERE id = %s
            ''', (conversation_id,))
            conn.commit()
        except Exception as e:
            print(f"Error updating conversation analytics: {str(e)}")
        finally:
            cur.close()
            conn.close()

    @staticmethod
    def update_user_analytics(user_id):
        """Update analytics for a user"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                WITH user_metrics AS (
                    SELECT 
                        COUNT(DISTINCT c.id)::float as total_conversations,
                        COUNT(DISTINCT CASE WHEN c.completion_status = 'completed' THEN c.id END)::float / 
                            NULLIF(COUNT(DISTINCT c.id)::float, 0) as completion_rate,
                        COUNT(m.id)::float as total_messages,
                        COALESCE(AVG(NULLIF(m.response_time, 0))::float, 0.0) as avg_response_time,
                        COALESCE(AVG(NULLIF(EXTRACT(EPOCH FROM (c.end_time - c.start_time))/60, 0))::float, 0.0) as avg_session_length,
                        MAX(c.start_time) as last_active,
                        COALESCE(AVG(NULLIF(m.word_count, 0))::float, 0.0) as avg_word_count
                    FROM conversations c
                    LEFT JOIN messages m ON c.id = m.conversation_id
                    WHERE c.user_id = %s
                )
                INSERT INTO analytics_summary (
                    user_id, total_conversations, total_messages,
                    average_response_time, average_session_length,
                    last_active, completion_rate, average_word_count,
                    updated_at
                )
                SELECT 
                    %s, total_conversations, total_messages,
                    avg_response_time, avg_session_length,
                    last_active, completion_rate, avg_word_count,
                    CURRENT_TIMESTAMP
                FROM user_metrics
                ON CONFLICT (user_id) DO UPDATE
                SET 
                    total_conversations = EXCLUDED.total_conversations,
                    total_messages = EXCLUDED.total_messages,
                    average_response_time = EXCLUDED.average_response_time,
                    average_session_length = EXCLUDED.average_session_length,
                    last_active = EXCLUDED.last_active,
                    completion_rate = EXCLUDED.completion_rate,
                    average_word_count = EXCLUDED.average_word_count,
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, user_id))
            conn.commit()
        except Exception as e:
            print(f"Error updating user analytics: {str(e)}")
        finally:
            cur.close()
            conn.close()

    @staticmethod
    def get_user_analytics(days=30):
        """Get analytics data for all users within specified days"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        start_date = datetime.now() - timedelta(days=days)
        
        cur.execute('''
            WITH daily_stats AS (
                SELECT 
                    DATE(c.start_time) as date,
                    COUNT(DISTINCT c.id)::float as conversations,
                    COUNT(DISTINCT c.user_id)::float as active_users,
                    COALESCE(AVG(NULLIF(m.response_time::float, 0))::float, 0.0) as avg_response_time,
                    COALESCE(AVG(NULLIF(EXTRACT(EPOCH FROM (c.end_time - c.start_time))/60, 0))::float, 0.0) as avg_session_length,
                    COALESCE(AVG(NULLIF(m.word_count::float, 0))::float, 0.0) as avg_word_count,
                    1::float as most_common_grade
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                WHERE c.start_time >= %s
                GROUP BY DATE(c.start_time)
            )
            SELECT * FROM daily_stats
            ORDER BY date DESC
        ''', (start_date,))
        
        results = cur.fetchall()
        cur.close()
        conn.close()
        
        return results
