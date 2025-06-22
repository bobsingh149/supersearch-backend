FROM paradedb/paradedb:latest

# Ensure we're running as root and fix apt permissions
USER root
RUN mkdir -p /var/lib/apt/lists/partial && \
    chmod 755 /var/lib/apt/lists/partial

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    pkg-config \
    jq \
    git \
    libssl-dev \
    openssl \
    libclang1 \
    libclang-dev \
    clang \
    llvm \
    llvm-dev \
    libpq-dev \
    postgresql-server-dev-all \
    cmake \
    libstdc++-12-dev \
    gcc-12 \
    g++-12 \
    && rm -rf /var/lib/apt/lists/*

# Install Rust and add to PATH
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Print version information
RUN echo '************* pg_config version *************' && \
    pg_config --version && \
    echo '************* psql version *************' && \
    psql --version

# Install cargo-pgrx and initialize
RUN cargo install --locked cargo-pgrx --version 0.12.5 && \
    cargo pgrx init --pg17 pg_config

# Install pgvectorscale
RUN cd /tmp && \
    git clone https://github.com/timescale/pgvectorscale && \
    cd pgvectorscale/pgvectorscale && \
    cargo pgrx install --release

# Clean up
RUN rm -rf /tmp 