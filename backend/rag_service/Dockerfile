# Use official Python image
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy only the requirements first (for caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --default-timeout=300 --retries=10 -r requirements.txt

# Copy the rest of the service code
COPY . ./rag_service

# Expose port for this service
EXPOSE 8002

# Set PYTHONPATH to include current directory so rag_service is recognized
ENV PYTHONPATH=/app

# Default command to run the service
CMD ["uvicorn", "rag_service.main:app", "--host", "0.0.0.0", "--port", "8002"]
