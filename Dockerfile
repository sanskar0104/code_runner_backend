FROM python:3.10-slim

# Install system deps
RUN apt-get update && apt-get install -y git && apt-get clean

# Set workdir
WORKDIR /app

# Copy all files
COPY . /app

# Install Python deps + Aider CLI
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install aider-chat

# Set environment variables for Gemini
ENV AIDER_MODEL=google/gemini-pro  # Use AI Studio Gemini

# Expose port
EXPOSE 10000

# Run FastAPI with Gunicorn
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "-w", "2", "-b", "0.0.0.0:10000"]
