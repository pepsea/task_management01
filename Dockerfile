FROM python:3.14-slim

# 日本時間で動かす（「今日のタスク」やメモの日付がずれないように）
ENV TZ=Asia/Tokyo \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_DB_PATH=/app/data/app.db

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY static ./static
# バージョン表示用: コミット番号（.git の HEAD・refs）と、イメージを作った日時
COPY .git ./.git
RUN date '+%Y-%m-%d %H:%M' > /app/BUILD_TIME

# アプリは root 以外のユーザー（appuser）で動かす。データは /app/data（docker-compose.yml でホストの ./data をつなぐ）。
# 起動時に docker-entrypoint.sh が /app/data の書き込み権限を整えてから appuser に切り替える
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app/data
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["docker-entrypoint.sh"]

EXPOSE 5003

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5003/api/health', timeout=2)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5003"]
