FROM node:18-alpine
WORKDIR /app
COPY package.json ./
COPY shared/ ./shared/
COPY services/billing/ ./services/billing/
RUN npm install --workspace=services/billing
EXPOSE 3014
CMD ["node", "services/billing/src/index.js"]
