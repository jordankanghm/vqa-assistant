# Use official Python image
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy only the requirements first (for caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the service code
COPY . .

# Expose port for this service
EXPOSE 8003

# Default command to run the service
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
