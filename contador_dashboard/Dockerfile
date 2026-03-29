# Imagen base de PHP CLI para Octane
FROM php:8.2-cli

# Instalar dependencias del sistema necesarias para compilar extensiones
RUN apt-get update && apt-get install -y \
    libpng-dev \
    libonig-dev \
    libxml2-dev \
    libzip-dev \
    libicu-dev \
    libcurl4-openssl-dev \
    libc-ares-dev \
    zip \
    unzip \
    git \
    curl \
    libsqlite3-dev \
    libpq-dev \
    dos2unix \
    libbrotli-dev \
    openssl \
    libssl-dev \
    gcc \
    make \
    autoconf \
    libc-dev \
    pkg-config \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Instalar extensiones de PHP base
RUN docker-php-ext-install pdo_mysql pdo_pgsql mbstring exif pcntl bcmath gd opcache intl zip sockets

# Instalar extensiones PECL (Swoole y Redis)
# Usamos una técnica más robusta para Swoole:
# 1. Bajamos la extensión. 2. La configuramos manualmente para asegurar que encuentre sockets.
RUN pecl install redis && docker-php-ext-enable redis \
    && cd /tmp && pecl download swoole \
    && mkdir -p /tmp/swoole && tar -xf swoole-*.tgz -C /tmp/swoole --strip-components=1 \
    && cd /tmp/swoole \
    && phpize \
    && ./configure --enable-sockets --enable-openssl --enable-swoole-curl --enable-cares --enable-brotli \
    && make -j$(nproc) && make install \
    && docker-php-ext-enable swoole \
    && rm -rf /tmp/swoole /tmp/swoole-*.tgz

# Establecer el directorio de trabajo
WORKDIR /var/www/html

# Copiar el archivo del entrypoint antes para poder usar dos2unix
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh && dos2unix /usr/local/bin/entrypoint.sh

# Copiar archivos de composer
COPY composer.json ./
# Copiamos el lock file si existe (el asterisco evita que falle si no existe en el contexto)
COPY composer.lock* ./

# Instalar Composer
COPY --from=composer:latest /usr/bin/composer /usr/bin/composer

# Instalamos todas las dependencias (incluyendo dev) para el entorno local.
# Usamos --no-scripts aquí porque el archivo 'artisan' aún no se ha copiado.
RUN composer install --no-interaction --optimize-autoloader --prefer-dist --no-scripts

# Copiar el resto del código
COPY . .

# Finalizar la instalación de composer y registrar paquetes
RUN composer dump-autoload --optimize && php artisan package:discover --ansi

# Crear directorios necesarios
RUN mkdir -p storage/framework/sessions \
    storage/framework/views \
    storage/framework/cache/data \
    storage/logs \
    bootstrap/cache

# Ajustar permisos
RUN chown -R www-data:www-data /var/www/html/storage /var/www/html/bootstrap/cache
RUN chmod -R 775 /var/www/html/storage /var/www/html/bootstrap/cache

# Configuración de OPcache
RUN { \
    echo 'opcache.enable_cli=1'; \
    echo 'opcache.memory_consumption=256'; \
    echo 'opcache.interned_strings_buffer=16'; \
    echo 'opcache.max_accelerated_files=20000'; \
    echo 'opcache.validate_timestamps=0'; \
    echo 'opcache.save_comments=1'; \
    echo 'opcache.fast_shutdown=1'; \
} > /usr/local/etc/php/conf.d/opcache-performance.ini

# Exponer el puerto de Octane (8000)
EXPOSE 8000

# Usar entrypoint y comando para arrancar Octane
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["php", "artisan", "octane:start", "--server=swoole", "--host=0.0.0.0", "--port=8000"]
