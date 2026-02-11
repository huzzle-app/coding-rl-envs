FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/analytics/ ./services/analytics/
RUN npm install --workspace=services/analytics
CMD ["node", "services/analytics/src/index.js"]
