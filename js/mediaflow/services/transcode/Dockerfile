FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy shared modules and service code
COPY shared/ ./shared/
COPY services/transcode/ ./services/transcode/

# Expose port
EXPOSE 3004

# Start service
CMD ["node", "services/transcode/src/index.js"]
