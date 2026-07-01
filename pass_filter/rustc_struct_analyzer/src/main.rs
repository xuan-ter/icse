#![feature(rustc_private)]

extern crate rustc_driver;
extern crate rustc_hir;
extern crate rustc_interface;
extern crate rustc_middle;
extern crate rustc_span;

use serde::Serialize;
use std::collections::BTreeMap;
use std::env;
use std::path::PathBuf;

use rustc_driver::{Callbacks, Compilation, RunCompiler};
use rustc_hir::intravisit::{walk_crate, walk_expr, Visitor};
use rustc_hir::{Expr, ExprKind};
use rustc_interface::interface;
use rustc_interface::Queries;
use rustc_middle::mir::{StatementKind, TerminatorKind};
use rustc_span::def_id::LOCAL_CRATE;

#[derive(Default, Serialize)]
struct HirFeatures {
    functions: u64,
    impl_blocks: u64,
    trait_items: u64,
    method_items: u64,
    expr_counts: BTreeMap<String, u64>,
}

#[derive(Default, Serialize)]
struct MirFeatures {
    bodies: u64,
    basic_blocks_total: u64,
    statements_total: u64,
    terminators_total: u64,
    statement_kinds: BTreeMap<String, u64>,
    terminator_kinds: BTreeMap<String, u64>,
}

#[derive(Serialize)]
struct FeatureReport {
    schema_version: u32,
    crate_name: String,
    hir: HirFeatures,
    mir: MirFeatures,
}

fn bump(map: &mut BTreeMap<String, u64>, key: impl Into<String>, n: u64) {
    let k = key.into();
    let v = map.entry(k).or_insert(0);
    *v += n;
}

struct HirCounter<'tcx> {
    tcx: rustc_middle::ty::TyCtxt<'tcx>,
    out: HirFeatures,
}

impl<'tcx> HirCounter<'tcx> {
    fn new(tcx: rustc_middle::ty::TyCtxt<'tcx>) -> Self {
        Self { tcx, out: HirFeatures::default() }
    }
}

impl<'tcx> Visitor<'tcx> for HirCounter<'tcx> {
    fn visit_item(&mut self, item: &'tcx rustc_hir::Item<'tcx>) {
        match item.kind {
            rustc_hir::ItemKind::Fn(..) => self.out.functions += 1,
            rustc_hir::ItemKind::Impl(..) => self.out.impl_blocks += 1,
            _ => {}
        }
        rustc_hir::intravisit::walk_item(self, item);
    }

    fn visit_trait_item(&mut self, item: &'tcx rustc_hir::TraitItem<'tcx>) {
        self.out.trait_items += 1;
        if matches!(item.kind, rustc_hir::TraitItemKind::Fn(..)) {
            self.out.method_items += 1;
        }
        rustc_hir::intravisit::walk_trait_item(self, item);
    }

    fn visit_impl_item(&mut self, item: &'tcx rustc_hir::ImplItem<'tcx>) {
        if matches!(item.kind, rustc_hir::ImplItemKind::Fn(..)) {
            self.out.method_items += 1;
        }
        rustc_hir::intravisit::walk_impl_item(self, item);
    }

    fn visit_expr(&mut self, expr: &'tcx Expr<'tcx>) {
        match expr.kind {
            ExprKind::Loop(..) => bump(&mut self.out.expr_counts, "Loop", 1),
            ExprKind::If(..) => bump(&mut self.out.expr_counts, "If", 1),
            ExprKind::Match(..) => bump(&mut self.out.expr_counts, "Match", 1),
            ExprKind::Call(..) => bump(&mut self.out.expr_counts, "Call", 1),
            ExprKind::MethodCall(..) => bump(&mut self.out.expr_counts, "MethodCall", 1),
            ExprKind::Index(..) => bump(&mut self.out.expr_counts, "Index", 1),
            ExprKind::Closure(..) => bump(&mut self.out.expr_counts, "Closure", 1),
            ExprKind::Await(..) => bump(&mut self.out.expr_counts, "Await", 1),
            ExprKind::Try(..) => bump(&mut self.out.expr_counts, "Try", 1),
            ExprKind::Binary(..) => bump(&mut self.out.expr_counts, "Binary", 1),
            ExprKind::Unary(..) => bump(&mut self.out.expr_counts, "Unary", 1),
            ExprKind::Block(..) => bump(&mut self.out.expr_counts, "Block", 1),
            _ => {}
        }
        walk_expr(self, expr);
    }
}

fn kind_name_from_debug<T: std::fmt::Debug>(k: &T) -> String {
    let s = format!("{k:?}");
    let head = s.split(['{', '(']).next().unwrap_or(&s);
    head.to_string()
}

fn terminator_key<'tcx>(k: &TerminatorKind<'tcx>) -> String {
    kind_name_from_debug(k)
}

fn statement_key<'tcx>(k: &StatementKind<'tcx>) -> String {
    kind_name_from_debug(k)
}

struct Analyzer {
    out_path: Option<PathBuf>,
    report: Option<FeatureReport>,
}

impl Analyzer {
    fn new(out_path: Option<PathBuf>) -> Self {
        Self { out_path, report: None }
    }
}

impl Callbacks for Analyzer {
    fn after_analysis<'tcx>(&mut self, _compiler: &interface::Compiler, queries: &'tcx Queries<'tcx>) -> Compilation {
        let out_path = self.out_path.clone();
        let mut report: Option<FeatureReport> = None;
        queries.global_ctxt().unwrap().enter(|tcx| {
            let crate_name = tcx.crate_name(LOCAL_CRATE).to_string();

            let hir = tcx.hir();
            let mut hir_counter = HirCounter::new(tcx);
            walk_crate(&mut hir_counter, hir.krate());

            let mut mir_out = MirFeatures::default();
            for def_id in tcx.body_owners() {
                mir_out.bodies += 1;
                let body = tcx.optimized_mir(def_id.to_def_id());
                mir_out.basic_blocks_total += body.basic_blocks.len() as u64;
                for bb in body.basic_blocks.iter() {
                    mir_out.statements_total += bb.statements.len() as u64;
                    for st in bb.statements.iter() {
                        bump(&mut mir_out.statement_kinds, statement_key(&st.kind), 1);
                    }
                    let t = bb.terminator();
                    mir_out.terminators_total += 1;
                    bump(&mut mir_out.terminator_kinds, terminator_key(&t.kind), 1);
                }
            }

            report = Some(FeatureReport { schema_version: 1, crate_name, hir: hir_counter.out, mir: mir_out });
        });

        if let Some(rep) = report.take() {
            if let Ok(json) = serde_json::to_string(&rep) {
                if let Some(path) = out_path {
                    let _ = std::fs::write(path, json);
                } else {
                    println!("{json}");
                }
            }
            self.report = Some(rep);
        }
        Compilation::Continue
    }
}

fn parse_out_path() -> Option<PathBuf> {
    if let Ok(p) = env::var("AUTO_TUNING_RUSTC_ANALYZER_OUT") {
        let s = p.trim();
        if !s.is_empty() {
            return Some(PathBuf::from(s));
        }
    }
    None
}

fn main() {
    let mut args: Vec<String> = env::args().collect();
    if args.len() >= 2 {
        if args[1].ends_with("rustc") || args[1].ends_with("rustc.exe") {
            let rustc = args.remove(1);
            args[0] = rustc;
        }
    }

    let out_path = parse_out_path();
    let mut callbacks = Analyzer::new(out_path);
    let _ = RunCompiler::new(&args, &mut callbacks).run();
}
