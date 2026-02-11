FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/connectors/ ./services/connectors/
RUN npm install --workspace=services/connectors
EXPOSE 3010
CMD ["node", "services/connectors/src/index.js"]
