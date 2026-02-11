FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/store/ ./services/store/
RUN npm install --workspace=services/store
EXPOSE 3006
CMD ["node", "services/store/src/index.js"]
