FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy shared modules and service code
COPY shared/ ./shared/
COPY services/catalog/ ./services/catalog/

# Expose port
EXPOSE 3005

# Start service
CMD ["node", "services/catalog/src/index.js"]
