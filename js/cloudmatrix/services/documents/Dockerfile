FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/documents/ ./services/documents/
RUN npm install --workspace=services/documents
CMD ["node", "services/documents/src/index.js"]
