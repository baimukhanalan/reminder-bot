FROM node:22-alpine AS web-build

WORKDIR /webapp
COPY webapp/package*.json ./
RUN npm ci
COPY webapp ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY assistant_bot ./assistant_bot
COPY --from=web-build /webapp/dist ./webapp/dist
RUN pip install --no-cache-dir .
RUN mkdir -p /app/data

CMD ["python", "-m", "assistant_bot.main"]
