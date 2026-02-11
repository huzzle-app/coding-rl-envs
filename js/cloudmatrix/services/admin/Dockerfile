FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/admin/ ./services/admin/
RUN npm install --workspace=services/admin
CMD ["node", "services/admin/src/index.js"]
