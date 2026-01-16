FROM httpd:2.4
# Copy our custom configuration file into the container.
COPY ./docker/httpd/httpd.conf /usr/local/apache2/conf/httpd.conf
COPY ./docker/httpd/proxy-http.conf /usr/local/apache2/conf/extra/proxy-http.conf
COPY ./docker/httpd/proxy-https.conf /usr/local/apache2/conf/extra/proxy-https.conf
COPY ./docker/httpd/proxy-locations.conf /usr/local/apache2/conf/extra/proxy-locations.conf