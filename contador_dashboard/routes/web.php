<?php
use Illuminate\Support\Facades\Route;
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\AreaController;
use App\Http\Controllers\EventController;

use App\Http\Controllers\Auth\LoginController;
// use App\Http\Controllers\UserController;

// Rutas Públicas de Auth
Route::get('/login', [LoginController::class, 'showLoginForm'])->name('login');
Route::post('/login', [LoginController::class, 'login'])->name('login.post');
Route::post('/logout', [LoginController::class, 'logout'])->name('logout');

// Rutas Protegidas
Route::middleware(['simpleAuth'])->group(function () {
    Route::get('/', [DashboardController::class, 'index'])->name('dashboard');
    Route::get('/data/live', [DashboardController::class, 'dataApi']);
    
    Route::get('/areas', [AreaController::class, 'index'])->name('areas.index');
    Route::middleware(['checkAdmin'])->group(function () {
        Route::resource('areas', AreaController::class)->only(['edit', 'update', 'destroy']);
    });
    
    Route::get('/eventos', [EventController::class, 'index'])->name('eventos.index');

/* 
    // Gestión de Usuarios (CRUD Completo) - Solo para Admins
    Route::middleware(['checkAdmin'])->group(function () {
        Route::resource('users', UserController::class);
    });
    */
});