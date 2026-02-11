FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/workers/ ./services/workers/
RUN npm install --workspace=services/workers
EXPOSE 3012
CMD ["node", "services/workers/src/index.js"]
