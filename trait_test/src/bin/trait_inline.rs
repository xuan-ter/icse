use std::env;
use std::hint::black_box;
use std::process::ExitCode;

use trait_test::{kernel_easy, kernel_mir_dependent, LayeredOp, SimpleOp};

const LEN: usize = 4096;
const ROUNDS: u32 = 64;

fn make_data(len: usize, seed: u32) -> Vec<u32> {
    let mut x = seed;
    let mut out = Vec::with_capacity(len);
    for _ in 0..len {
        x = x.wrapping_mul(1664525).wrapping_add(1013904223);
        out.push(x);
    }
    out
}

fn run_easy(repeat: u32) -> u32 {
    let data = make_data(LEN, 0x1234_5678);
    let op = SimpleOp { seed: 0xA5A5_5A5A };
    let mut sum = 0u32;

    for _ in 0..repeat {
        sum = sum.wrapping_add(kernel_easy(black_box(&op), black_box(&data), ROUNDS));
    }

    black_box(sum)
}

fn run_mir_dependent(repeat: u32) -> u32 {
    let data = make_data(LEN, 0xDEAD_BEEF);
    let op = LayeredOp { seed: 0x1357_9BDF };
    let mut sum = 0u32;

    for _ in 0..repeat {
        sum = sum.wrapping_add(kernel_mir_dependent(black_box(&op), black_box(&data), ROUNDS));
    }

    black_box(sum)
}

fn parse_args() -> Result<(String, u32), String> {
    let mut case_name = String::new();
    let mut repeat = 1u32;

    let mut args = env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--case" => {
                case_name = args.next().ok_or("missing value for --case")?;
            }
            "--repeat" => {
                let value = args.next().ok_or("missing value for --repeat")?;
                repeat = value
                    .parse::<u32>()
                    .map_err(|_| "invalid integer for --repeat".to_string())?;
            }
            _ => return Err(format!("unknown argument: {arg}")),
        }
    }

    if case_name.is_empty() {
        return Err("missing --case".to_string());
    }
    if repeat == 0 {
        return Err("--repeat must be >= 1".to_string());
    }

    Ok((case_name, repeat))
}

fn main() -> ExitCode {
    let (case_name, repeat) = match parse_args() {
        Ok(parsed) => parsed,
        Err(err) => {
            eprintln!("{err}");
            return ExitCode::FAILURE;
        }
    };

    let sum = match case_name.as_str() {
        "easy_case" => run_easy(repeat),
        "mir_dependent_case" => run_mir_dependent(repeat),
        _ => {
            eprintln!("unknown case: {case_name}");
            return ExitCode::FAILURE;
        }
    };

    black_box(sum);
    ExitCode::SUCCESS
}
