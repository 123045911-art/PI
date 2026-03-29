@extends('layouts.app')
@section('title', 'Estado General del Sistema')
@section('content')
    <div class="row mb-4">
        {{-- Total de Personas Dentro del Sistema --}}
        <div class="col-md-6 col-lg-3 mb-3">
            <div class="card kpi-card-custom bg-kpi-total">
                <div class="card-body d-flex justify-content-between align-items-center">
                    <div>
                        <p class="card-title text-white-75 mb-1">Total dentro</p>
                        <div class="kpi-value-custom" id="kpi-total-personas">{{ $kpis['total_personas'] }}</div>
                        <p class="card-text text-white-50">Personas en todas las áreas</p>
                    </div>
                    <i class="fas fa-users kpi-icon-custom"></i>
                </div>
            </div>
        </div>
        {{-- Áreas Activas --}}
        <div class="col-md-6 col-lg-3 mb-3">
            <div class="card kpi-card-custom bg-kpi-active">
                <div class="card-body d-flex justify-content-between align-items-center">
                    <div>
                        <p class="card-title text-white-75 mb-1">Áreas activas</p>
                        <div class="kpi-value-custom" id="kpi-areas-activas">{{ $kpis['areas_activas'] }}</div>
                        <p class="card-text text-white-50">Áreas con conteo > 0</p>
                    </div>
                    <i class="fas fa-boxes kpi-icon-custom"></i>
                </div>
            </div>
        </div>
        {{-- Entradas del día --}}
        <div class="col-md-6 col-lg-3 mb-3">
            <div class="card kpi-card-custom bg-kpi-enter">
                <div class="card-body d-flex justify-content-between align-items-center">
                    <div>
                        <p class="card-title text-white-75 mb-1">Entradas (Hoy)</p>
                        <div class="kpi-value-custom" id="kpi-entradas-hoy">{{ $kpis['entradas_hoy'] }}</div>
                        <p class="card-text text-white-50">Eventos 'enter' del día</p>
                    </div>
                    <i class="fas fa-sign-in-alt kpi-icon-custom"></i>
                </div>
            </div>
        </div>
        {{-- Salidas del día --}}
        <div class="col-md-6 col-lg-3 mb-3">
            <div class="card kpi-card-custom bg-kpi-exit">
                <div class="card-body d-flex justify-content-between align-items-center">
                    <div>
                        <p class="card-title text-white-75 mb-1">Salidas (Hoy)</p>
                        <div class="kpi-value-custom" id="kpi-salidas-hoy">{{ $kpis['salidas_hoy'] }}</div>
                        <p class="card-text text-white-50">Eventos 'exit' del día</p>
                    </div>
                    <i class="fas fa-sign-out-alt kpi-icon-custom"></i>
                </div>
            </div>
        </div>
    </div>
    {{-- Gráfico y Eventos Recientes --}}
    <div class="row">
        {{-- Gráfico de Conteo en Tiempo Real por Área --}}
        <div class="col-lg-8 mb-4">
            <div class="card shadow-sm h-100 rounded-4">
                <div class="card-body">
                    <h4 class="card-title mb-3">Conteo de personas actual por área</h4>
                    <div style="height: 400px;">
                        <canvas id="conteoChart"></canvas>
                    </div>
                </div>
            </div>
        </div>
        {{-- Tabla de Eventos Recientes --}}
        <div class="col-lg-4 mb-4">
            <div class="card shadow-sm h-100 rounded-4 d-flex flex-column">
                <div class="card-header bg-white border-bottom fw-bold">
                    Últimos eventos registrados
                </div>
                <div class="card-body p-0 flex-grow-1">
                    <div class="table-responsive event-table-container">
                        <table class="table table-sm table-hover mb-0">
                            <thead>
                                <tr>
                                    <th>Hora</th>
                                    <th>Área</th>
                                    <th>Evento</th>
                                    <th>Track ID</th>
                                </tr>
                            </thead>
                            <tbody id="eventos-table-body">
                                {{-- Se llena dinámicamente vía JS --}}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>
@endsection

{{-- Lógica de Gráfico y Actualización en Tiempo Real --}}
@push('scripts')
<script>
    document.addEventListener('DOMContentLoaded', function () {
        const ctx = document.getElementById('conteoChart').getContext('2d');
        let conteoChart;
        const apiUrl = '{{ url('/data/live') }}';
        const initialData = @json($estados_areas->map(fn($area) => [
            'name' => $area->name,
            'count' => $area->estado->people_count ?? 0,
        ]));

        // Función para inicializar el gráfico
        function initChart(data) {
            const labels = data.map(item => item.name);
            const counts = data.map(item => item.count);
            conteoChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Conteo de Personas',
                        data: counts,
                        backgroundColor: 'rgba(54, 162, 235, 0.6)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: function (value) {
                                    if (Number.isInteger(value)) {
                                        return value;
                                    }
                                },
                                stepSize: 1
                            }
                        }
                    },
                    plugins: {
                        legend: { display: false },
                        title: { display: true, text: 'Personas por Área' }
                    }
                }
            });
        }

        // Inicializar el gráfico con datos estáticos del primer render
        initChart(initialData);

        // Función para actualizar los datos desde la API
        function updateDashboard() {
            fetch(apiUrl)
                .then(response => response.json())
                .then(data => {
                    // Actualizar todos los KPIs
                    document.getElementById('kpi-total-personas').textContent = data.total_personas;
                    document.getElementById('kpi-areas-activas').textContent = data.areas_activas;
                    document.getElementById('kpi-entradas-hoy').textContent = data.entradas_hoy;
                    document.getElementById('kpi-salidas-hoy').textContent = data.salidas_hoy;

                    // Actualizar Tabla de Eventos Recientes
                    const eventosBody = document.getElementById('eventos-table-body');
                    let newTableHtml = '';
                    if (data.eventos_recientes && data.eventos_recientes.length > 0) {
                        data.eventos_recientes.forEach(evento => {
                            const badgeClass = evento.event === 'ENTER' ? 'bg-success' : 'bg-danger';
                            newTableHtml += `
                                <tr>
                                    <td>${evento.hora}</td>
                                    <td>${evento.area_name}</td>
                                    <td>
                                        <span class="badge ${badgeClass}">
                                            ${evento.event}
                                        </span>
                                    </td>
                                    <td>${evento.track_id}</td>
                                </tr>
                            `;
                        });
                    } else {
                        newTableHtml = '<tr><td colspan="4" class="text-center text-muted">Sin eventos recientes</td></tr>';
                    }
                    eventosBody.innerHTML = newTableHtml;

                    // Actualizar Gráfico
                    if (data.conteo_por_area && data.conteo_por_area.length > 0) {
                        const newLabels = data.conteo_por_area.map(item => item.name);
                        const newCounts = data.conteo_por_area.map(item => item.count);
                        conteoChart.data.labels = newLabels;
                        conteoChart.data.datasets[0].data = newCounts;
                        conteoChart.update();
                    }
                })
                .catch(error => console.error('Error al actualizar dashboard:', error));
        }

        // Cargar datos iniciales inmediatamente
        updateDashboard();

        // Actualización en tiempo real cada 3 segundos
        setInterval(updateDashboard, 3000);
    });
</script>
@endpush