# Use slim Python 3.11 image
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Install curl (needed for wait-for script)
RUN apt-get update \
    && apt-get install -y curl \
    && rm -rf /var/lib/apt/lists/*

# Copy integration tests
COPY . .

# Install dependencies
RUN pip install --no-cache-dir pytest requests

# Make wait-for script executable
RUN chmod +x wait-for.sh

# Run the integration test by default
CMD ["./wait-for.sh", \
     "http://gateway:8000/docs", \
     "http://inference_service:8001/docs", \
     "http://rag_service:8002/docs", \
     "http://user_service:8003/docs", \
     "--", \
     "pytest", "test_integration.py", "--maxfail=1", "--disable-warnings", "-q"]
