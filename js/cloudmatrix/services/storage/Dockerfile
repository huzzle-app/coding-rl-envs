FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/storage/ ./services/storage/
RUN npm install --workspace=services/storage
CMD ["node", "services/storage/src/index.js"]
