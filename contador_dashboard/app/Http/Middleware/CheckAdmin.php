<?php
// d:\PI\contador_dashboard\app\Http\Middleware\CheckAdmin.php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Session;
use Symfony\Component\HttpFoundation\Response;

class CheckAdmin
{
    /**
     * Handle an incoming request.
     *
     * @param  \Closure(\Illuminate\Http\Request): (\Symfony\Component\HttpFoundation\Response)  $next
     */
    public function handle(Request $request, Closure $next): Response
    {
        if (!Session::get('is_admin')) {
            return redirect()->route('dashboard')->with('error', 'Acceso denegado: Se requieren permisos de administrador.');
        }

        return $next($request);
    }
}
