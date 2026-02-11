FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/alerts/ ./services/alerts/
RUN npm install --workspace=services/alerts
EXPOSE 3008
CMD ["node", "services/alerts/src/index.js"]
