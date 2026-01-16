# Stage 1: Unpacker
# Use a debian base to align with other services for better CI caching.
FROM debian:bookworm-slim AS unpacker

# Install unzip utility
#RUN apt-get update && \
#    apt-get install -y --no-install-recommends unzip && \
#    rm -rf /var/lib/apt/lists/*

WORKDIR /tmp

# Copy the single extension zip file from the build context
#COPY ./keycloak/target/keycloak-extension-*.zip .
# Unzip the contents
#RUN unzip keycloak-extension-*.zip

RUN mkdir /data
RUN mkdir /data/import
COPY ./docker/keycloak/data/import/realm-export.json ./data/import/

# Stage 2: Builder
# This stage prepares the Keycloak server with our custom providers and themes.
FROM quay.io/keycloak/keycloak:26.4.6 AS builder

# Set build-time configuration using ENV. These options will be baked into the optimized image.
ENV KC_DB=postgres
ENV KC_HTTP_RELATIVE_PATH=/keycloak

# Copy the custom realm, themes, and providers from the unpacker stage
COPY --from=unpacker /tmp/data/import/realm-export.json /opt/keycloak/data/import/
#COPY --from=unpacker /tmp/themes/ /opt/keycloak/themes/
#COPY --from=unpacker /tmp/providers/ /opt/keycloak/providers/

# Run the Keycloak build command to install providers and optimize the server.
RUN /opt/keycloak/bin/kc.sh build

# Stage 3: Final Image
# This stage creates the final, clean image.
FROM quay.io/keycloak/keycloak:26.4.6

# Copy the optimized server from the builder stage
COPY --from=builder /opt/keycloak/ /opt/keycloak/

# Set the entrypoint to the Keycloak start script
ENTRYPOINT ["/opt/keycloak/bin/kc.sh"]
