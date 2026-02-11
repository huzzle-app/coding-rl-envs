FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/gateway/ ./services/gateway/
RUN npm install --workspace=services/gateway
EXPOSE 3000
CMD ["node", "services/gateway/src/index.js"]
