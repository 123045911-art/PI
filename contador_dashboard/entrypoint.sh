#!/bin/bash
set -e

echo "==> Preparando Laravel Dashboard..."

# Entrar al directorio de trabajo
cd /var/www/html

# Crear directorios de storage si no existen
mkdir -p storage/framework/sessions
mkdir -p storage/framework/views
mkdir -p storage/framework/cache/data
mkdir -p storage/logs
mkdir -p bootstrap/cache

# Establecer permisos (ignorar errores en Windows volumes)
# Apache usa el usuario www-data (uid 33 en esta imagen)
# Si estamos en un volume mount, chown puede fallar.
chown -R www-data:www-data storage bootstrap/cache 2>/dev/null || true
chmod -R 775 storage bootstrap/cache 2>/dev/null || true

# Usamos COMPOSER_DISCARD_CHANGES para evitar errores de "uncommitted changes" en volúmenes de Windows
export COMPOSER_DISCARD_CHANGES=true

# Verificar si el comando octane está disponible. Si no, sincronizamos vendor.
if ! php artisan list | grep -q "octane:"; then
    echo "==> Octane no detectado o vendor incompleto. Sincronizando dependencias..."
    composer install --no-interaction --optimize-autoloader --prefer-dist
    php artisan package:discover --ansi
fi

# Verificar que .env existe
if [ ! -f ".env" ]; then
    echo "==> Creando .env desde .env.example..."
    cp .env.example .env
fi

# Generar APP_KEY si no existe
if ! grep -q "^APP_KEY=base64:" .env 2>/dev/null; then
    echo "==> Generando APP_KEY..."
    php artisan key:generate --force --no-interaction
fi

# Asegurar que Octane está instalado y configurado
if [ ! -f "config/octane.php" ]; then
    echo "==> Instalando configuración de Octane..."
    php artisan octane:install --server=swoole --no-interaction
fi

# Limpiar cachés
php artisan config:clear --no-interaction || true
php artisan route:clear --no-interaction || true
php artisan view:clear --no-interaction || true

echo "==> Laravel listo. Iniciando Octane en modo Swoole..."

# Iniciar Octane (exec para que reciba señales de Docker)
exec "$@"
