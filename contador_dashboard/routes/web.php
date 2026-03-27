<?php
use Illuminate\Support\Facades\Route;
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\AreaController;
use App\Http\Controllers\EventController;

Route::get('/', [DashboardController::class, 'index']);
Route::get('/data/live', [DashboardController::class, 'dataApi']);
Route::resource('areas', AreaController::class)->only(['index', 'edit', 'update', 'destroy']);
Route::get('/eventos', [EventController::class, 'index'])->name('eventos.index');