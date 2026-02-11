FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/query/ ./services/query/
RUN npm install --workspace=services/query
EXPOSE 3007
CMD ["node", "services/query/src/index.js"]
