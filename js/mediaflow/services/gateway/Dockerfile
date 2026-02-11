FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy shared modules and service code
COPY shared/ ./shared/
COPY services/gateway/ ./services/gateway/

# Expose port
EXPOSE 3000

# Start service
CMD ["node", "services/gateway/src/index.js"]
