FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/versions/ ./services/versions/
RUN npm install --workspace=services/versions
CMD ["node", "services/versions/src/index.js"]
