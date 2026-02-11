FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/router/ ./services/router/
RUN npm install --workspace=services/router
EXPOSE 3004
CMD ["node", "services/router/src/index.js"]
