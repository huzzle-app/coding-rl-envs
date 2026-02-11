FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/scheduler/ ./services/scheduler/
RUN npm install --workspace=services/scheduler
EXPOSE 3011
CMD ["node", "services/scheduler/src/index.js"]
