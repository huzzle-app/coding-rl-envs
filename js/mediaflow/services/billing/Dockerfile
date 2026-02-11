FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy shared modules and service code
COPY shared/ ./shared/
COPY services/billing/ ./services/billing/

# Expose port
EXPOSE 3008

# Start service
CMD ["node", "services/billing/src/index.js"]
