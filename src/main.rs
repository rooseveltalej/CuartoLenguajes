use actix_web::{web, App, HttpServer, Responder, HttpResponse, get, post};
use serde::{Serialize, Deserialize};
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use actix_cors::Cors;
use tokio::time::{sleep, Duration};
use rand::Rng;
use uuid::Uuid;
use log::{info, error};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
enum SeatState {
    Libre,
    Reservado,
    ReservadoPorUsuario,
    Comprado,
    ReservadoTemporalmente, // Nuevo estado
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
struct Seat {
    estado: SeatState,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
enum CategoriaZona {
    VIP,
    Regular,
    Sol,
    Platea,
}

#[derive(Debug, Serialize, Deserialize)]
struct Zone {
    nombre: String,
    categorias: HashMap<CategoriaZona, Vec<Vec<Seat>>>,
}

#[derive(Debug, Serialize, Deserialize)]
struct Estadio {
    zonas: Vec<Zone>,
}

#[derive(Deserialize)]
struct SearchRequest {
    categoria: String,
    cantidad: usize,
}

#[derive(Serialize)]
struct AvailableSeats {
    zona: String,
    categoria: String,
    asientos: Vec<(usize, usize)>, // (fila, número)
}

#[derive(Debug, Deserialize)]
struct ReservaTemporalRequest {
    zona: String,
    categoria: String,
    asientos: Vec<(usize, usize)>, // (fila, asiento)
}

#[derive(Debug, Deserialize)]
struct ConfirmarCompraRequest {
    reserva_id: String,
}

#[derive(Debug, Deserialize)]
struct ProcesarPagoRequest {
    metodo_pago: String,
    detalles: serde_json::Value, // Los detalles pueden variar según el método
}

#[derive(Serialize)]
struct ProcesarPagoResponse {
    aprobado: bool,
    mensaje: String,
}

#[derive(Debug, Clone)]
struct ReservaTemporal {
    asientos: Vec<(String, CategoriaZona, usize, usize)>, // (zona, categoría, fila, asiento)
    tiempo_expiracion: std::time::Instant,
}

impl Estadio {
    fn new() -> Self {
        let zona_a = Zone {
            nombre: String::from("A"),
            categorias: Self::crear_categorias(),
        };
        let zona_b = Zone {
            nombre: String::from("B"),
            categorias: Self::crear_categorias(),
        };
        let zona_c = Zone {
            nombre: String::from("C"),
            categorias: Self::crear_categorias(),
        };
        let zona_d = Zone {
            nombre: String::from("D"),
            categorias: Self::crear_categorias(),
        };

        Estadio {
            zonas: vec![zona_a, zona_b, zona_c, zona_d],
        }
    }

    fn crear_categorias() -> HashMap<CategoriaZona, Vec<Vec<Seat>>> {
        let mut categorias = HashMap::new();
        categorias.insert(
            CategoriaZona::VIP,
            Self::crear_matriz_asientos(
                3,
                5,
                vec![(0, 0, SeatState::Reservado), (1, 2, SeatState::Comprado)],
            ),
        );
        categorias.insert(
            CategoriaZona::Regular,
            Self::crear_matriz_asientos(
                7,
                5,
                vec![(0, 1, SeatState::Libre), (2, 3, SeatState::Reservado)],
            ),
        );
        categorias.insert(
            CategoriaZona::Sol,
            Self::crear_matriz_asientos(
                5,
                5,
                vec![(2, 2, SeatState::Comprado), (4, 4, SeatState::Libre)],
            ),
        );
        categorias.insert(
            CategoriaZona::Platea,
            Self::crear_matriz_asientos(
                6,
                5,
                vec![(3, 3, SeatState::Libre), (2, 2, SeatState::Reservado)],
            ),
        );
        categorias
    }

    fn crear_matriz_asientos(
        filas: usize,
        asientos_por_fila: usize,
        estados: Vec<(usize, usize, SeatState)>,
    ) -> Vec<Vec<Seat>> {
        let mut matriz = vec![vec![Seat { estado: SeatState::Libre }; asientos_por_fila]; filas];

        for (fila, numero, estado) in estados {
            if fila < filas && numero < asientos_por_fila {
                matriz[fila][numero].estado = estado;
            }
        }

        matriz
    }

    fn calcular_ocupacion(&self, zona: &Zone) -> f64 {
        let mut total_asientos = 0;
        let mut asientos_ocupados = 0;

        for asientos in zona.categorias.values() {
            for fila in asientos {
                total_asientos += fila.len();
                for asiento in fila {
                    if asiento.estado != SeatState::Libre {
                        asientos_ocupados += 1;
                    }
                }
            }
        }

        if total_asientos == 0 {
            1.0 // Si no hay asientos, consideramos la zona como llena
        } else {
            asientos_ocupados as f64 / total_asientos as f64
        }
    }

    fn buscar_asientos_consecutivos(
        &self,
        categoria_buscar: &str,
        cantidad: usize,
    ) -> Option<AvailableSeats> {
        let categoria_zona = match categoria_buscar {
            "VIP" => CategoriaZona::VIP,
            "Regular" => CategoriaZona::Regular,
            "Sol" => CategoriaZona::Sol,
            "Platea" => CategoriaZona::Platea,
            _ => return None,
        };

        // Calcular ocupación de cada zona
        let mut zonas_con_ocupacion: Vec<(&Zone, f64)> = self
            .zonas
            .iter()
            .map(|zona| (zona, self.calcular_ocupacion(zona)))
            .collect();

        // Ordenar zonas por ocupación ascendente
        zonas_con_ocupacion.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap());

        for (zona, _) in zonas_con_ocupacion {
            if let Some(asientos) = zona.categorias.get(&categoria_zona) {
                // Buscar en cada fila
                for (fila_idx, fila) in asientos.iter().enumerate() {
                    let mut asientos_consecutivos = Vec::new();
                    let mut count = 0;

                    // Buscar asientos consecutivos en la fila
                    for (asiento_idx, asiento) in fila.iter().enumerate() {
                        if asiento.estado == SeatState::Libre {
                            count += 1;
                            asientos_consecutivos.push((fila_idx, asiento_idx));

                            if count == cantidad {
                                return Some(AvailableSeats {
                                    zona: zona.nombre.clone(),
                                    categoria: categoria_buscar.to_string(),
                                    asientos: asientos_consecutivos,
                                });
                            }
                        } else {
                            count = 0;
                            asientos_consecutivos.clear();
                        }
                    }
                }
            }
        }
        None
    }
}

type SharedEstadio = Arc<Mutex<Estadio>>;
type SharedReservasTemporales = Arc<Mutex<HashMap<String, ReservaTemporal>>>;

#[get("/")]
async fn health_check() -> impl Responder {
    HttpResponse::Ok().body("Servidor corriendo correctamente.")
}

#[get("/get_stadium_structure")]
async fn get_stadium_structure(data: web::Data<SharedEstadio>) -> impl Responder {
    let estadio = data.lock().unwrap();
    HttpResponse::Ok().json(&*estadio)
}

#[post("/buscar_asientos")]
async fn buscar_asientos(
    data: web::Data<SharedEstadio>,
    info: web::Json<SearchRequest>,
) -> impl Responder {
    let estadio = data.lock().unwrap();

    match estadio.buscar_asientos_consecutivos(&info.categoria, info.cantidad) {
        Some(asientos) => HttpResponse::Ok().json(asientos),
        None => {
            HttpResponse::NotFound().body("No se encontraron asientos consecutivos disponibles")
        }
    }
}

#[post("/reservar_asientos_temporalmente")]
async fn reservar_asientos_temporalmente(
    data: web::Data<SharedEstadio>,
    reservas: web::Data<SharedReservasTemporales>,
    info: web::Json<ReservaTemporalRequest>,
) -> impl Responder {
    info!("Solicitud para reservar asientos temporalmente: {:?}", info);

    let mut estadio = data.lock().unwrap();
    let mut reservas_temporales = reservas.lock().unwrap();

    let categoria_zona = match info.categoria.as_str() {
        "VIP" => CategoriaZona::VIP,
        "Regular" => CategoriaZona::Regular,
        "Sol" => CategoriaZona::Sol,
        "Platea" => CategoriaZona::Platea,
        _ => return HttpResponse::BadRequest().body("Categoría inválida."),
    };

    // Verificar y actualizar el estado de los asientos
    for zona in &mut estadio.zonas {
        if zona.nombre == info.zona {
            if let Some(asientos_categoria) = zona.categorias.get_mut(&categoria_zona) {
                for (fila, asiento) in &info.asientos {
                    if *fila < asientos_categoria.len()
                        && *asiento < asientos_categoria[*fila].len()
                    {
                        let seat = &mut asientos_categoria[*fila][*asiento];
                        if seat.estado == SeatState::Libre {
                            seat.estado = SeatState::ReservadoTemporalmente;
                        } else {
                            return HttpResponse::BadRequest()
                                .body("Uno o más asientos no están disponibles.");
                        }
                    } else {
                        return HttpResponse::BadRequest().body("Asiento fuera de rango.");
                    }
                }
            }
        }
    }

    // Generar un ID único para la reserva
    let reserva_id = Uuid::new_v4().to_string();

    // Crear la reserva temporal
    let reserva = ReservaTemporal {
        asientos: info
            .asientos
            .iter()
            .map(|(fila, asiento)| (info.zona.clone(), categoria_zona.clone(), *fila, *asiento))
            .collect(),
        tiempo_expiracion: std::time::Instant::now() + Duration::from_secs(300), // 5 minutos
    };

    reservas_temporales.insert(reserva_id.clone(), reserva);

    // Iniciar el temporizador para liberar los asientos después de 5 minutos
    let data_clone = data.clone();
    let reservas_clone = reservas.clone();
    let reserva_id_clone = reserva_id.clone();

    tokio::spawn(async move {
        sleep(Duration::from_secs(300)).await; // Esperar 5 minutos

        let mut estadio = data_clone.lock().unwrap();
        let mut reservas_temporales = reservas_clone.lock().unwrap();

        if let Some(reserva) = reservas_temporales.remove(&reserva_id_clone) {
            for (zona_nombre, categoria, fila, asiento) in reserva.asientos {
                for zona in &mut estadio.zonas {
                    if zona.nombre == zona_nombre {
                        if let Some(asientos_categoria) = zona.categorias.get_mut(&categoria) {
                            let seat = &mut asientos_categoria[fila][asiento];
                            if seat.estado == SeatState::ReservadoTemporalmente {
                                seat.estado = SeatState::Libre;
                                info!(
                                    "Asiento liberado automáticamente: Zona {}, Categoría {:?}, Fila {}, Asiento {}",
                                    zona_nombre, categoria, fila, asiento
                                );
                            }
                        }
                    }
                }
            }
        }
    });

    HttpResponse::Ok().json(serde_json::json!({ "reserva_id": reserva_id }))
}

#[post("/confirmar_compra")]
async fn confirmar_compra(
    data: web::Data<SharedEstadio>,
    reservas: web::Data<SharedReservasTemporales>,
    info: web::Json<ConfirmarCompraRequest>,
) -> impl Responder {
    info!("Solicitud para confirmar compra: {:?}", info);

    let mut estadio = data.lock().unwrap();
    let mut reservas_temporales = reservas.lock().unwrap();

    if let Some(reserva) = reservas_temporales.remove(&info.reserva_id) {
        for (zona_nombre, categoria, fila, asiento) in reserva.asientos {
            for zona in &mut estadio.zonas {
                if zona.nombre == zona_nombre {
                    if let Some(asientos_categoria) = zona.categorias.get_mut(&categoria) {
                        let seat = &mut asientos_categoria[fila][asiento];
                        if seat.estado == SeatState::ReservadoTemporalmente {
                            seat.estado = SeatState::Comprado;
                            info!(
                                "Asiento comprado: Zona {}, Categoría {:?}, Fila {}, Asiento {}",
                                zona_nombre, categoria, fila, asiento
                            );
                        }
                    }
                }
            }
        }
        // Devolver true en caso de éxito
        return HttpResponse::Ok().body("true");
    } else {
        // Devolver false en caso de error
        return HttpResponse::Ok().body("false");
    }
}

#[post("/procesar_pago")]
async fn procesar_pago(info: web::Json<ProcesarPagoRequest>) -> impl Responder {
    info!("Procesando pago: {:?}", info);

    // Generar un valor booleano aleatorio
    let mut rng = rand::thread_rng();
    let aprobado = rng.gen_bool(0.8); // 80% de probabilidad de aprobación

    // Devolver "true" o "false" como texto plano
    if aprobado {
        HttpResponse::Ok().body("true")
    } else {
        HttpResponse::Ok().body("false")
    }
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    env_logger::init();

    let estadio = Arc::new(Mutex::new(Estadio::new()));
    let reservas_temporales = Arc::new(Mutex::new(HashMap::<String, ReservaTemporal>::new()));


    HttpServer::new(move || {
        let cors = Cors::default()
            .allow_any_origin()
            .allow_any_method()
            .allow_any_header()
            .supports_credentials();

        App::new()
            .wrap(cors)
            .app_data(web::Data::new(Arc::clone(&estadio)))
            .app_data(web::Data::new(Arc::clone(&reservas_temporales)))
            .service(health_check)
            .service(get_stadium_structure)
            .service(buscar_asientos)
            .service(reservar_asientos_temporalmente)
            .service(confirmar_compra)
            .service(procesar_pago)
    })
    .bind("127.0.0.1:8080")?
    .run()
    .await
}
