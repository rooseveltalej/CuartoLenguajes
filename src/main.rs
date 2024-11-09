use actix_web::{web, App, HttpServer, Responder, HttpResponse, get, post, Result};
use serde::{Serialize, Deserialize};
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use actix_cors::Cors;


#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
enum SeatState {
    Libre,
    Reservado,
    ReservadoPorUsuario,
    Comprado,
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
        categorias.insert(CategoriaZona::VIP, Self::crear_matriz_asientos(3, 5, vec![(0, 0, SeatState::Reservado), (1, 2, SeatState::Comprado)]));
        categorias.insert(CategoriaZona::Regular, Self::crear_matriz_asientos(7, 5, vec![(0, 1, SeatState::Libre), (2, 3, SeatState::Reservado)]));
        categorias.insert(CategoriaZona::Sol, Self::crear_matriz_asientos(5, 5, vec![(2, 2, SeatState::Comprado), (4, 4, SeatState::Libre)]));
        categorias.insert(CategoriaZona::Platea, Self::crear_matriz_asientos(6, 5, vec![(3, 3, SeatState::Libre), (2, 2, SeatState::Reservado)]));
        categorias
    }

    fn crear_matriz_asientos(filas: usize, asientos_por_fila: usize, estados: Vec<(usize, usize, SeatState)>) -> Vec<Vec<Seat>> {
        let mut matriz = vec![vec![Seat { estado: SeatState::Libre }; asientos_por_fila]; filas];

        for (fila, numero, estado) in estados {
            if fila < filas && numero < asientos_por_fila {
                matriz[fila][numero].estado = estado;
            }
        }

        matriz
    }
}

#[derive(Deserialize)]
struct SeatRequest {
    categoria: String,
    zona: String,
    fila: usize,
    asiento: usize,
}

type SharedEstadio = Arc<Mutex<Estadio>>;

#[get("/")]
async fn health_check() -> impl Responder {
    HttpResponse::Ok().body("Servidor corriendo correctamente.")
}

#[get("/get_stadium_structure")]
async fn get_stadium_structure(data: web::Data<SharedEstadio>) -> impl Responder {
    let estadio = data.lock().unwrap();
    HttpResponse::Ok().json(&*estadio)
}

#[post("/reserve_seat")]
async fn reserve_seat(data: web::Data<SharedEstadio>, info: web::Json<SeatRequest>) -> impl Responder {
    let SeatRequest { categoria, zona, fila, asiento } = info.into_inner();
    let mut estadio = data.lock().unwrap();

    for zona_obj in &mut estadio.zonas {
        if zona_obj.nombre == zona {
            if let Some(asientos) = zona_obj.categorias.get_mut(&CategoriaZona::VIP) { // Cambiar para usar la categoría correcta
                if fila > 0 && fila <= asientos.len() && asiento > 0 && asiento <= asientos[0].len() {
                    let current_seat = &mut asientos[fila - 1][asiento - 1];
                    if current_seat.estado == SeatState::Libre {
                        current_seat.estado = SeatState::ReservadoPorUsuario;
                        return HttpResponse::Ok().body("Asiento reservado con éxito.");
                    } else {
                        return HttpResponse::BadRequest().body("El asiento no está disponible para reserva.");
                    }
                }
            }
        }
    }

    HttpResponse::NotFound().body("Asiento no encontrado o fuera de rango.")
    }

    #[actix_web::main]
    async fn main() -> std::io::Result<()> {
        let estadio = Arc::new(Mutex::new(Estadio::new()));

        HttpServer::new(move || {
            let cors = Cors::default()
            .allow_any_origin()
            .allow_any_method()
            .allow_any_header()
            .supports_credentials();

            App::new()
                .wrap(cors)
                .app_data(web::Data::new(Arc::clone(&estadio)))
                .service(health_check)
                .service(get_stadium_structure)
                .service(reserve_seat)
        })
        .bind("127.0.0.1:8080")?
        .run()
        .await
    }