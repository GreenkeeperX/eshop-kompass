FROM python:3.13-alpine

# Unprivilegierter Benutzer; /data gehört ihm, damit ein neues Volume beschreibbar ist
RUN addgroup -g 10001 app && adduser -D -H -u 10001 -G app app \
    && mkdir /data && chown app:app /data

WORKDIR /srv
COPY app ./app
ENV DATA_DIR=/data PORT=8787 PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
VOLUME /data
EXPOSE 8787
USER 10001:10001
# Zustand für Docker und Portainer (1.7.32): /healthz prüft Datenordner und Zeitplan, ohne data.json
# zu lesen. wget aus BusyBox ist im Image, kein Zusatzpaket; Fehlercode bei 503 oder ohne Antwort
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s --retries=3 \
    CMD wget -q -T 4 -O /dev/null "http://127.0.0.1:${PORT}/healthz" || exit 1
CMD ["python", "-m", "app.server"]
