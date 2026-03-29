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

# Verificar que vendor existe (para volume mounts que sobreescriben)
if [ ! -d "vendor" ]; then
    echo "==> Instalando dependencias de Composer..."
    composer install --no-interaction --no-dev --optimize-autoloader
fi

# Verificar que .env existe
if [ ! -f ".env" ]; then
    echo "==> Creando .env desde .env.example..."
    cp .env.example .env
fi

# Generar APP_KEY si no existe en el .env y no está en el ambiente
# Si APP_KEY ya tiene un valor, no hacemos nada.
if ! grep -q "^APP_KEY=base64:" .env 2>/dev/null; then
    echo "==> Generando APP_KEY..."
    php artisan key:generate --force --no-interaction
fi

# Limpiar cachés y asegurar que use el API
# No corremos migraciones porque no hay DB.
php artisan config:clear --no-interaction 2>/dev/null || true
php artisan route:clear --no-interaction 2>/dev/null || true
php artisan view:clear --no-interaction 2>/dev/null || true

echo "==> Laravel listo. Iniciando Apache..."

# Iniciar Apache (exec para que reciba señales de Docker)
exec "$@"
