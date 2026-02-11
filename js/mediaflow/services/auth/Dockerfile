FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy shared modules and service code
COPY shared/ ./shared/
COPY services/auth/ ./services/auth/

# Expose port
EXPOSE 3001

# Start service
CMD ["node", "services/auth/src/index.js"]
