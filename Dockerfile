FROM python:3.10-slim

# ✅ Installs Git (required by Aider)
RUN apt-get update && apt-get install -y git && apt-get clean

# ✅ Set working directory
WORKDIR /app

# ✅ Copy backend files
COPY . /app

# ✅ Install Python + Aider CLI
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install aider-chat

# ✅ Set environment for Gemini 1.5 Pro model
ENV AIDER_MODEL=gemini/gemini-1.5-pro-latest

# ✅ Expose correct port
EXPOSE 10000

# ✅ Start with Gunicorn and UvicornWorker
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "-t", "300", "-b", "0.0.0.0:10000"]
