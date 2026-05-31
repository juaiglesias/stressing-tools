FROM php:8.3-cli

RUN apt-get update && apt-get install -y \
    curl git unzip zip libssl-dev libbrotli-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pecl install swoole \
    && docker-php-ext-enable swoole

RUN docker-php-ext-install pcntl

COPY --from=composer:2 /usr/bin/composer /usr/bin/composer

WORKDIR /app

RUN composer create-project laravel/laravel . --prefer-dist --no-dev --quiet

RUN composer require laravel/octane --no-interaction --quiet

RUN php artisan octane:install --server=swoole --no-interaction

COPY routes/api.php routes/api.php
COPY bootstrap/app.php bootstrap/app.php

RUN php artisan config:cache && php artisan route:cache

EXPOSE 3000
CMD ["php", "artisan", "octane:start", "--server=swoole", "--host=0.0.0.0", "--port=3000", "--workers=4"]
