FROM httpd:2.4
# Copy our custom configuration file into the container.
COPY ./docker-macos/httpd/httpd.conf /usr/local/apache2/conf/httpd.conf
COPY ./docker-macos/httpd/proxy-http.conf /usr/local/apache2/conf/extra/proxy-http.conf
COPY ./docker-macos/httpd/proxy-https.conf /usr/local/apache2/conf/extra/proxy-https.conf
COPY ./docker-macos/httpd/proxy-locations.conf /usr/local/apache2/conf/extra/proxy-locations.conf