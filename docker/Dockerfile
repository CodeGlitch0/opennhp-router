# One pinned OpenNHP build. Select an image with --target. Cipher scheme 0.
FROM golang:1.26 AS opennhp

ARG OPENNHP_REF=0115f5ff729c8791b2ae1d0daf11f34c4c0f31cf
ENV GOTOOLCHAIN=auto

RUN git clone https://github.com/OpenNHP/opennhp.git /src/opennhp \
    && git -C /src/opennhp checkout ${OPENNHP_REF}

COPY docker/keygen /src/opennhp/cmd/opennhp-keygen
COPY plugins/authclient /src/authclient

WORKDIR /src/opennhp
RUN make init \
    && make acd \
    && make serverd \
    && make relayd \
    && go build -o /out/opennhp-keygen ./cmd/opennhp-keygen

WORKDIR /src/authclient
RUN go build -buildmode=plugin -o /out/authclient.so .

FROM ubuntu:22.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        python3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=opennhp /out/opennhp-keygen /opt/opennhp-keygen
COPY docker/entrypoint.py /entrypoint.py
COPY opennhp_router /opt/opennhp_router/opennhp_router
RUN chmod 755 /opt/opennhp-keygen /entrypoint.py

ENV PYTHONPATH=/opt/opennhp_router
ENV OPENNHP_KEYGEN=/opt/opennhp-keygen

FROM runtime AS gateway

RUN apt-get update && apt-get install -y --no-install-recommends \
        iptables \
        ipset \
    && rm -rf /var/lib/apt/lists/*

COPY --from=opennhp /src/opennhp/release/nhp-ac /opt/nhp-ac
COPY docker/forwarder.py /opt/forwarder.py
COPY docker/iptables-deny.sh /iptables-deny.sh
RUN chmod 755 /iptables-deny.sh /opt/forwarder.py

ENTRYPOINT ["python3", "/entrypoint.py", "gateway"]

FROM runtime AS server

COPY --from=opennhp /src/opennhp/release/nhp-server /opt/nhp-server
COPY --from=opennhp /out/authclient.so /opt/nhp-server/plugins/authclient/authclient.so

ENTRYPOINT ["python3", "/entrypoint.py", "server"]

FROM runtime AS auth

EXPOSE 8090
ENTRYPOINT ["python3", "/entrypoint.py", "auth"]

FROM runtime AS relay

COPY --from=opennhp /src/opennhp/release/nhp-relay /opt/nhp-relay

ENTRYPOINT ["python3", "/entrypoint.py", "relay"]
