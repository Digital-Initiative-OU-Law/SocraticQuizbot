# QuizBot

A Socratic learning QuizBot using Streamlit and OpenAI API for PDF-based educational dialogues.

## Author
Created by Sean Harrington  
Director of Technology Innovation  
University of Oklahoma College of Law
https://law.ou.edu/faculty-and-staff/sean-harrington

## Features
- PDF processing with support for complex formatting
- Socratic dialogue generation using OpenAI GPT-4
- Student analytics and engagement tracking (1-3 grade scale based on interaction level)
- Instructor dashboard for content management
- Multi-user support with role-based access
- Conversation history and transcript generation
- Optional Ollama integration for local LLM support

## Installation

### Requirements
- Python 3.8+
- PostgreSQL database
- OpenAI API key (or Ollama for local LLM support)

### Environment Setup

1. Create a `.env` file in the root directory using `.env.example` as a template:
   ```bash
   cp .env.example .env
   ```

2. Configure your environment variables in the `.env` file:

   #### Required Variables:
   ```env
   # OpenAI Configuration (if not using Ollama)
   OPENAI_API_KEY=your_openai_api_key

   # PostgreSQL Database Configuration
   PGDATABASE=your_database_name
   PGUSER=your_database_user
   PGPASSWORD=your_database_password
   PGHOST=localhost
   PGPORT=5432
   ```

   #### Optional Ollama Configuration:
   ```env
   # Set these only if using Ollama instead of OpenAI
   USE_OLLAMA=true
   OLLAMA_HOST=http://localhost:11434
   OLLAMA_MODEL=[insert name of model]
   ```

   #### Note on Models
   The current chat completions are tailored for OpenAI.  If you are using a local model (llama7b, Mistral7b, etc.) you will have to adjust services/openai_service.py to conform to your model's requirements.

### Local Setup
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up PostgreSQL database:
   ```sql
   CREATE DATABASE quizbot;
   CREATE USER quizbot_user WITH PASSWORD 'your_password';
   GRANT ALL PRIVILEGES ON DATABASE quizbot TO quizbot_user;
   ```
4. Configure environment variables as described above
5. Run the application: `streamlit run main.py`

## Usage
1. Place your PDF materials in the Readings folder
2. Start a new quiz to engage in Socratic dialogue
3. View analytics and download conversation transcripts

Note: The application will process any PDF files placed in the Readings folder automatically.

## Ollama Integration (Alternative to OpenAI)

QuizBot can be configured to use Ollama as an alternative to OpenAI for local LLM support. This is useful for:
- Running without internet connectivity
- Privacy-sensitive environments
- Cost-free operation
- Testing and development

### Setting up Ollama

1. Install Ollama:
   ```bash
   # Linux
   curl -fsSL https://ollama.com/install.sh | sh
   
   # For MacOS and Windows, download from https://ollama.com
   ```

2. Pull the required model:
   ```bash
   ollama pull mistral:7b
   ```

3. Install Python dependencies:
   ```bash
   pip install ollama langchain
   ```

4. Configure QuizBot for Ollama:
   - Set `USE_OLLAMA=true` in your environment variables
   - No OpenAI API key required when using Ollama

### Using Ollama with QuizBot

1. Start the Ollama service:
   ```bash
   ollama serve
   ```

2. Run QuizBot normally:
   ```bash
   streamlit run main.py
   ```

The application will automatically use the local Ollama model for:
- Generating questions
- Processing responses
- Creating summaries
- Managing dialogue flow

Note: When using Ollama, response times may vary depending on your hardware. GPU support is recommended for optimal performance.

## Troubleshooting

### Common Issues:

1. Database Connection:
   - Verify PostgreSQL is running
   - Check database credentials in .env
   - Ensure database exists and user has proper permissions

2. OpenAI API:
   - Verify API key is valid
   - Check for API rate limits
   - Ensure internet connectivity

3. Ollama Integration:
   - Verify Ollama service is running
   - Check if model is downloaded
   - Confirm USE_OLLAMA setting

### Error Messages:

- "Database connection failed": Check PostgreSQL configuration
- "OpenAI API error": Verify API key and rate limits
- "Ollama service not found": Ensure Ollama is running

For additional support, please open an issue on GitHub.
