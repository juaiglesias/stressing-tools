FROM php:8.3-cli

RUN apt-get update && apt-get install -y \
    curl git unzip zip \
    && rm -rf /var/lib/apt/lists/*

COPY --from=composer:2 /usr/bin/composer /usr/bin/composer

WORKDIR /app

RUN composer create-project laravel/laravel . --prefer-dist --no-dev --quiet

COPY routes/api.php routes/api.php
COPY bootstrap/app.php bootstrap/app.php

RUN php artisan config:cache && php artisan route:cache

EXPOSE 3000
CMD ["php", "artisan", "serve", "--host=0.0.0.0", "--port=3000"]
