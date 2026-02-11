FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/search/ ./services/search/
RUN npm install --workspace=services/search
CMD ["node", "services/search/src/index.js"]
