FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/permissions/ ./services/permissions/
RUN npm install --workspace=services/permissions
CMD ["node", "services/permissions/src/index.js"]
