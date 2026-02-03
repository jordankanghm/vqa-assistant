# Use slim Python 3.11 image
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Install curl (needed for wait-for script)
RUN apt-get update \
    && apt-get install -y curl \
    && rm -rf /var/lib/apt/lists/*

# Copy rag_service package
COPY rag_service ./rag_service

# Copy integration tests
COPY integration ./integration

# Install dependencies
RUN pip install --default-timeout=300 --retries=10 -r integration/requirements.txt

# Make wait-for script executable
RUN chmod +x ./integration/wait-for.sh

# Set PYTHONPATH to include current directory so rag_service is recognized
ENV PYTHONPATH=/app

# Run the integration test by default
CMD ["sh", "./integration/wait-for.sh", \
     "http://gateway:8000/docs", \
     "http://inference_service:8001/docs", \
     "http://rag_service:8002/docs", \
     "http://user_service:8003/docs", \
     "--", \
     "pytest", "integration/test_integration.py", "--maxfail=1", "--disable-warnings", "-q"]
