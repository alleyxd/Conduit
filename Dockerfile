FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY conduit ./conduit
RUN pip install --no-cache-dir .

COPY servers ./servers
COPY examples ./examples
COPY servers.json ./
RUN python examples/make_data.py

ENTRYPOINT ["conduit"]
