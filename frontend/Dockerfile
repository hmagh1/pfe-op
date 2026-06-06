FROM node:20-alpine

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

ARG VITE_API_BASE_URL=http://127.0.0.1:18000/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

EXPOSE 15175

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "15175"]