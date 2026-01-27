# Use Node 20 slim image
FROM node:20-slim

# Set working directory inside the container
WORKDIR /app

# Install curl (needed for wait-for script)
RUN apt-get update \
    && apt-get install -y curl \
    && rm -rf /var/lib/apt/lists/*

# Copy package.json and package-lock.json first (for caching)
COPY package*.json ./

# Install dependencies (including Playwright)
RUN npm install
RUN npx playwright install --with-deps

# Copy all e2e test files
COPY . .

# Wait for services before running tests
CMD ["sh", "./wait-for.sh", \
     "http://frontend:80/", \
     "http://gateway:8000/docs", \
     "http://inference_service:8001/docs", \
     "http://rag_service:8002/docs", \
     "http://user_service:8003/docs", \
     "--", \
     "npx", "playwright", "test", "--reporter=dot"]
