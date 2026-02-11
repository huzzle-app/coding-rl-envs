FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/comments/ ./services/comments/
RUN npm install --workspace=services/comments
CMD ["node", "services/comments/src/index.js"]
