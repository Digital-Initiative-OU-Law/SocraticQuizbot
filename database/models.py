import psycopg2
import os
from services.settings import USE_PGVECTOR

def get_db_connection():
    return psycopg2.connect(
        dbname=os.environ['PGDATABASE'],
        user=os.environ['PGUSER'],
        password=os.environ['PGPASSWORD'],
        host=os.environ['PGHOST'],
        port=os.environ['PGPORT']
    )

def column_exists(cur, table: str, column: str) -> bool:
    """Check if a column exists in a table"""
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = %s AND column_name = %s
        );
    """, (table, column))
    return cur.fetchone()[0]

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Create users table
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(200) NOT NULL,
                first_name VARCHAR(100),
                last_name VARCHAR(100),
                role VARCHAR(20) DEFAULT 'student',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Add OpenAI API key column if it doesn't exist (legacy plaintext storage)
        if not column_exists(cur, 'users', 'openai_api_key'):
            cur.execute('''
                ALTER TABLE users 
                ADD COLUMN openai_api_key VARCHAR(200)
            ''')

        # Add encrypted OpenAI API key column if it doesn't exist (preferred)
        if not column_exists(cur, 'users', 'openai_api_key_enc'):
            cur.execute('''
                ALTER TABLE users
                ADD COLUMN openai_api_key_enc BYTEA
            ''')
        
        # Create conversations table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                title VARCHAR(200),
                context TEXT,
                course VARCHAR(100),
                week VARCHAR(50),
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                response_count INTEGER DEFAULT 0,
                average_response_time FLOAT DEFAULT 0,
                completion_status VARCHAR(20) DEFAULT 'ongoing',
                sentence_count INTEGER DEFAULT 0,
                model_backend VARCHAR(50),
                model_name VARCHAR(100),
                prompt_template_version VARCHAR(50)
            )
        """)
        
        # Create messages table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                conversation_id INTEGER REFERENCES conversations(id),
                role VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sentence_count INTEGER DEFAULT 0,
                response_time FLOAT DEFAULT NULL,
                word_count INTEGER DEFAULT 0
            )
        """)
        
        # Create analytics_summary table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS analytics_summary (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) UNIQUE,
                total_conversations INTEGER DEFAULT 0,
                total_messages INTEGER DEFAULT 0,
                average_response_time FLOAT DEFAULT 0,
                average_session_length FLOAT DEFAULT 0,
                last_active TIMESTAMP,
                completion_rate FLOAT DEFAULT 0,
                interaction_grade INTEGER DEFAULT 1,
                average_word_count FLOAT DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()

        # Optional retrieval schema
        if USE_PGVECTOR:
            try:
                # Enable extension and create tables
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS documents (
                        id SERIAL PRIMARY KEY,
                        course VARCHAR(100),
                        week VARCHAR(50),
                        filename TEXT,
                        md5 CHAR(32) UNIQUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS chunks (
                        id SERIAL PRIMARY KEY,
                        document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
                        chunk_index INTEGER,
                        content TEXT,
                        embedding vector(1536)
                    );
                    """
                )
                cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);")
                conn.commit()
            except Exception as e:
                print(f"Retrieval schema init warning: {str(e)}")
                conn.rollback()
        
    except Exception as e:
        print(f"Database initialization error: {str(e)}")
        conn.rollback()
        
    finally:
        cur.close()
        conn.close()
