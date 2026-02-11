FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/dashboards/ ./services/dashboards/
RUN npm install --workspace=services/dashboards
EXPOSE 3009
CMD ["node", "services/dashboards/src/index.js"]
