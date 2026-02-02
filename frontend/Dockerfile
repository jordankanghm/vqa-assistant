# Step 1: Build the React app
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package.json and lockfile first for caching
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source files
COPY . .

# Build production static files
RUN npm run build

# Step 2: Serve with nginx
FROM nginx:alpine

# Copy built files from builder
COPY --from=builder /app/build /usr/share/nginx/html

# Expose port 80
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
