use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::Instant;

use serde_json::json;
use tokio_postgres::NoTls;

struct Query {
    name: String,
    sql: String,
}

fn load_queries(dir: &Path) -> Vec<Query> {
    let mut files: Vec<PathBuf> = fs::read_dir(dir)
        .unwrap_or_else(|error| panic!("cannot read {}: {error}", dir.display()))
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| path.extension().is_some_and(|extension| extension == "sql"))
        .collect();
    files.sort();

    files
        .iter()
        .map(|path| {
            let text = fs::read_to_string(path).unwrap();
            let stem = path.file_stem().unwrap().to_string_lossy();
            let name = stem
                .trim_start_matches(|character: char| character.is_ascii_digit() || character == '_')
                .to_string();
            let sql = text
                .lines()
                .filter(|line| !line.trim_start().starts_with("--"))
                .collect::<Vec<_>>()
                .join("\n")
                .trim()
                .trim_end_matches(';')
                .to_string();
            Query { name, sql }
        })
        .collect()
}

fn percentile(sorted: &[f64], fraction: f64) -> f64 {
    if sorted.len() == 1 {
        return sorted[0];
    }
    let position = (sorted.len() - 1) as f64 * fraction;
    let low = position.floor() as usize;
    let high = (low + 1).min(sorted.len() - 1);
    sorted[low] + (sorted[high] - sorted[low]) * (position - low as f64)
}

fn argument(args: &[String], name: &str, default: &str) -> String {
    args.iter()
        .position(|value| value == name)
        .and_then(|index| args.get(index + 1))
        .cloned()
        .unwrap_or_else(|| default.to_string())
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = env::args().collect();
    let dsn = argument(&args, "--dsn", "postgresql://postgres@localhost:5432/cesi");
    let queries_dir = PathBuf::from(argument(&args, "--queries", "queries"));
    let repeats: usize = argument(&args, "--repeats", "3").parse()?;
    let warmup: usize = argument(&args, "--warmup", "1").parse()?;
    let out = PathBuf::from(argument(&args, "--out", "rust/results.json"));

    let queries = load_queries(&queries_dir);
    if queries.is_empty() {
        return Err(format!("no query found in {}", queries_dir.display()).into());
    }

    let (client, connection) = tokio_postgres::connect(&dsn, NoTls).await?;
    tokio::spawn(async move {
        if let Err(error) = connection.await {
            eprintln!("connection error: {error}");
        }
    });

    client.batch_execute("SET jit = off").await?;
    client.batch_execute("VACUUM (ANALYZE)").await?;

    let mut results = Vec::new();
    for query in &queries {
        for _ in 0..warmup {
            client.query(query.sql.as_str(), &[]).await?;
        }

        let mut samples = Vec::with_capacity(repeats);
        let mut rows = 0;
        for _ in 0..repeats {
            let started = Instant::now();
            rows = client.query(query.sql.as_str(), &[]).await?.len();
            samples.push(started.elapsed().as_secs_f64() * 1000.0);
        }

        let mut sorted = samples.clone();
        sorted.sort_by(|left, right| left.partial_cmp(right).unwrap());
        let median = percentile(&sorted, 0.5);
        results.push(json!({
            "name": query.name,
            "median_ms": (median * 100.0).round() / 100.0,
            "p95_ms": (percentile(&sorted, 0.95) * 100.0).round() / 100.0,
            "min_ms": (sorted[0] * 100.0).round() / 100.0,
            "max_ms": (sorted[sorted.len() - 1] * 100.0).round() / 100.0,
            "rows": rows,
            "samples_ms": sorted.iter().map(|value| (value * 100.0).round() / 100.0).collect::<Vec<_>>(),
        }));
    }

    let document = json!({
        "engine": "postgres",
        "repeats": repeats,
        "warmup": warmup,
        "results": results,
    });
    if let Some(parent) = out.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(&out, serde_json::to_string_pretty(&document)? + "\n")?;

    println!("{}", serde_json::to_string_pretty(&document)?);
    eprintln!("results: {}", out.display());
    Ok(())
}
