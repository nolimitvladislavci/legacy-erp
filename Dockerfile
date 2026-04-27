FROM ubuntu:24.04
RUN apt-get update -qq &&     apt-get install -y --no-install-recommends       python3.12 python3.12-venv libpq5 curl     && ln -sf /usr/bin/python3.12 /usr/bin/python3     && rm -rf /var/lib/apt/lists/*
