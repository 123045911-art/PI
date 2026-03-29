# Imagen base de PHP con Apache
FROM php:8.2-apache

# Instalar dependencias del sistema y extensiones de PHP necesarias
# Añadimos libpq-dev para Postgre (aunque Laravel no use la DB, las extensiones a veces se quejan si no están instaladas)
# Añadimos dos2unix para manejar Windows line endings en scripts
RUN apt-get update && apt-get install -y \
    libpng-dev \
    libonig-dev \
    libxml2-dev \
    zip \
    unzip \
    git \
    curl \
    libsqlite3-dev \
    libpq-dev \
    dos2unix \
    && docker-php-ext-install pdo_mysql pdo_pgsql mbstring exif pcntl bcmath gd \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Habilitar mod_rewrite de Apache para Laravel
RUN a2enmod rewrite

# Establecer el directorio de trabajo
WORKDIR /var/www/html

# Copiar el archivo del entrypoint antes para poder usar dos2unix
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh && dos2unix /usr/local/bin/entrypoint.sh

# Copiar solo archivos de dependencia primero para aprovechar la caché de Docker
COPY composer.json composer.lock ./

# Instalar Composer para las dependencias de PHP
COPY --from=composer:latest /usr/bin/composer /usr/bin/composer
RUN composer install --no-interaction --no-scripts --no-autoloader --no-dev

# Copiar el resto del código del proyecto
COPY . .

# Finalizar la instalación de composer (esto crea la carpeta vendor si no existe)
RUN composer dump-autoload --optimize --no-dev

# Crear directorios necesarios de storage y bootstrap
RUN mkdir -p storage/framework/sessions \
    storage/framework/views \
    storage/framework/cache/data \
    storage/logs \
    bootstrap/cache

# Ajustar los permisos. En build time usamos el usuario base. 
# En runtime el entrypoint intentará ajustar con www-data.
RUN chown -R www-data:www-data /var/www/html/storage /var/www/html/bootstrap/cache
RUN chmod -R 775 /var/www/html/storage /var/www/html/bootstrap/cache

# Configurar Apache para que sirva desde la carpeta public/
ENV APACHE_DOCUMENT_ROOT /var/www/html/public
RUN sed -ri -e 's!/var/www/html!${APACHE_DOCUMENT_ROOT}!g' /etc/apache2/sites-available/*.conf
RUN sed -ri -e 's!/var/www/!${APACHE_DOCUMENT_ROOT}!g' /etc/apache2/apache2.conf /etc/apache2/conf-available/*.conf

# Exponer el puerto 80 (Apache)
EXPOSE 80

# Usar entrypoint para inicialización y luego arrancar Apache
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["apache2-foreground"]
