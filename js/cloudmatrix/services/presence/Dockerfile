FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/presence/ ./services/presence/
RUN npm install --workspace=services/presence
CMD ["node", "services/presence/src/index.js"]
