FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/emulators/src

WORKDIR /app

COPY 02-emulators/src /app/emulators/src
COPY 01-contracts /app/contracts

ARG INSTALL_KAFKA=false
RUN if [ "$INSTALL_KAFKA" = "true" ]; then \
      python -m pip install "azure-identity>=1.17,<2" "confluent-kafka>=2.5,<3"; \
    fi

USER 65532:65532

ENTRYPOINT ["python", "-m", "mda_emulators.cli"]
CMD ["--scenario", "/app/contracts/examples/scenario.integrated-defense.json", "--transport", "stdout"]
