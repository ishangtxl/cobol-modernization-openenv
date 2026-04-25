FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends gnucobol ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /oracle

COPY INVOICE_ORACLE.cbl TAXRATE.cbl INVOICE_REC.cpy TAX_CODE.cpy ./
RUN cobc -x -free -o invoice_oracle INVOICE_ORACLE.cbl TAXRATE.cbl

WORKDIR /work
ENTRYPOINT ["/oracle/invoice_oracle"]
