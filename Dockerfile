# Use lightweight official Python image
FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Set container working directory
WORKDIR /app

# Install dependencies first for optimal Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application files to container
COPY . .

# Expose port for Google Cloud Run
EXPOSE 8080

# Launch application using production-ready Gunicorn server
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
