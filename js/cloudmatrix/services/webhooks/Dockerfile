FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/webhooks/ ./services/webhooks/
RUN npm install --workspace=services/webhooks
CMD ["node", "services/webhooks/src/index.js"]
