use axum::{
    extract::Query,
    routing::{get, post},
    Json, Router,
};
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::HashMap;
use tokio::time::{sleep, Duration};

const MOD: i64 = 1_000_000_007;

fn cpu_compute(n: usize) -> i64 {
    let derived: Vec<i64> = (0..n)
        .map(|i| ((i as i64 * 31) % 1000 * 2 + 1) % 1000)
        .collect();

    let mut checksum: i64 = 0;
    for i in 0..n {
        for j in 0..n {
            checksum = (checksum + derived[i] * derived[j]) % MOD;
        }
    }

    let c = 64usize;
    for i in 0..c {
        for j in 0..c {
            let mut s: i64 = 0;
            for k in 0..c {
                s += ((i * c + k) % 100) as i64 * ((k + j) % 100) as i64;
            }
            checksum = (checksum + s) % MOD;
        }
    }
    checksum
}

async fn holamundo() -> Json<Value> {
    Json(json!({"mensaje": "hola mundo"}))
}

async fn dbquery() -> Json<Value> {
    sleep(Duration::from_millis(25)).await;
    let rows: Vec<Value> = (0..10).map(|k| json!({"id": k, "value": k * 10})).collect();
    Json(json!({"rows": rows}))
}

#[derive(Deserialize)]
struct NParam {
    n: Option<usize>,
}

async fn cpucompute(Query(params): Query<NParam>) -> Json<Value> {
    let n = params.n.unwrap_or(200);
    let checksum = cpu_compute(n);
    Json(json!({"checksum": checksum, "n": n}))
}

async fn memalloc(Query(params): Query<NParam>) -> Json<Value> {
    let n = params.n.unwrap_or(20000);
    let arr: Vec<Value> = (0..n)
        .map(|i| {
            json!({
                "id": i,
                "name": format!("item-{}", i),
                "tags": [i, i + 1, i + 2],
                "payload": {"a": i % 100, "b": (i * 2) % 100, "c": (i * 3) % 100}
            })
        })
        .collect();

    let sum: usize = (0..n).map(|i| i % 100).sum();
    let sample_len = n.min(100);

    Json(json!({"count": n, "sum": sum, "sample": &arr[..sample_len]}))
}

#[derive(Deserialize)]
struct PayloadItem {
    id: i64,
    name: String,
    value: i64,
    active: bool,
}

#[derive(Deserialize)]
struct PayloadBody {
    items: Vec<PayloadItem>,
    #[allow(dead_code)]
    meta: Option<HashMap<String, Value>>,
}

async fn payload(Json(body): Json<PayloadBody>) -> Json<Value> {
    let active_count = body.items.iter().filter(|it| it.active).count();
    let total: i64 = body.items.iter().filter(|it| it.active).map(|it| it.value).sum();

    let limit = body.items.len().min(10);
    let sample: Vec<Value> = body.items[..limit]
        .iter()
        .map(|it| json!({"id": it.id, "name": it.name.to_uppercase(), "value": it.value}))
        .collect();

    Json(json!({
        "received": body.items.len(),
        "activeCount": active_count,
        "total": total,
        "sample": sample
    }))
}

#[tokio::main]
async fn main() {
    let app = Router::new()
        .route("/holamundo", get(holamundo))
        .route("/dbquery", get(dbquery))
        .route("/cpucompute", get(cpucompute))
        .route("/memalloc", get(memalloc))
        .route("/payload", post(payload));

    let listener = tokio::net::TcpListener::bind("0.0.0.0:3000").await.unwrap();
    axum::serve(listener, app).await.unwrap();
}
