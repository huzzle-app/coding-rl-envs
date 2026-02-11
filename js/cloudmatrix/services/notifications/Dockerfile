FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/notifications/ ./services/notifications/
RUN npm install --workspace=services/notifications
CMD ["node", "services/notifications/src/index.js"]
