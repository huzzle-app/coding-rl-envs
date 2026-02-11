FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/transform/ ./services/transform/
RUN npm install --workspace=services/transform
EXPOSE 3003
CMD ["node", "services/transform/src/index.js"]
