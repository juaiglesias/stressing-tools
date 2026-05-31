FROM php:8.3-fpm

RUN apt-get update && apt-get install -y \
    nginx supervisor curl git unzip zip \
    && rm -rf /var/lib/apt/lists/*

COPY --from=composer:2 /usr/bin/composer /usr/bin/composer

WORKDIR /app

RUN composer create-project laravel/laravel . --prefer-dist --no-dev --quiet

COPY routes/api.php routes/api.php
COPY bootstrap/app.php bootstrap/app.php

RUN php artisan config:cache && php artisan route:cache

RUN chown -R www-data:www-data /app/storage /app/bootstrap/cache

COPY www.conf /usr/local/etc/php-fpm.d/www.conf
COPY nginx.conf /etc/nginx/sites-available/default
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 3000
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
