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

# Set correct model
ENV AIDER_MODEL=gemini/gemini-1.5-pro-latest

# Expose port
EXPOSE 10000

# Run FastAPI with Gunicorn
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "-t", "300", "-b", "0.0.0.0:10000"]

