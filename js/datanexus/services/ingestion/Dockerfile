FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/ingestion/ ./services/ingestion/
RUN npm install --workspace=services/ingestion
EXPOSE 3002
CMD ["node", "services/ingestion/src/index.js"]
