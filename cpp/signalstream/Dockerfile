FROM ubuntu:22.04 AS builder

ARG SERVICE=gateway

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    build-essential cmake git curl zip unzip tar pkg-config \
    libpq-dev libssl-dev librdkafka-dev \
    bison flex autoconf automake libtool \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/microsoft/vcpkg.git /opt/vcpkg && \
    /opt/vcpkg/bootstrap-vcpkg.sh
ENV VCPKG_ROOT=/opt/vcpkg
ENV PATH="${VCPKG_ROOT}:${PATH}"

WORKDIR /app
COPY . .

RUN cmake -B build \
    -DCMAKE_TOOLCHAIN_FILE=${VCPKG_ROOT}/scripts/buildsystems/vcpkg.cmake \
    -DCMAKE_BUILD_TYPE=Release && \
    cmake --build build --parallel $(nproc)

FROM ubuntu:22.04 AS runtime
ARG SERVICE=gateway
RUN apt-get update && apt-get install -y libpq5 librdkafka1 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/build/services/${SERVICE}/${SERVICE} /usr/local/bin/
EXPOSE 8000-8009
CMD /usr/local/bin/${SERVICE}
