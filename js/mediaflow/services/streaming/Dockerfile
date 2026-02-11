FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy shared modules and service code
COPY shared/ ./shared/
COPY services/streaming/ ./services/streaming/

# Expose port
EXPOSE 3006

# Start service
CMD ["node", "services/streaming/src/index.js"]
