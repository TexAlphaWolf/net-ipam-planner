FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MPLCONFIGDIR=/tmp/matplotlib

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install . \
    && useradd --system --no-create-home --uid 10001 ipam \
    && install -d -o ipam /data

# Plans and results are in /data (a volume or a bind mount). Nothing needs the network or a privilege: run with
# --network none, --read-only, --cap-drop ALL and --tmpfs /tmp (matplotlib's cache).
USER ipam
WORKDIR /data
VOLUME ["/data"]
ENTRYPOINT ["ipam"]
CMD ["--help"]
