
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.ticker as ticker
import os
from pathlib import Path

def get_color(model_tag):
    colors = {
        'DCOPF': '#d62728',  # red
        'Jabr': '#1f77b4',   # blue
        'Shor': '#2ca02c',   # green
        'ChordalShor': '#9467bd',  # purple
        'QC4': '#8c564b',    # brown
        'QC6': '#e377c2',    # pink
        'QC8': '#7f7f7f',   # gray
        'QC10': '#bcbd22',   # olive
    }
    return colors.get(model_tag, 'black')

def get_marker(model_tag):
    markers = {
        'DCOPF': 'o',
        'Jabr': 's',
        'Shor': '^',
        'ChordalShor': 'v',
        'QC4': 'p',
        'QC6': 'h',
        'QC8': '*',
        'QC10': 'X'
    }
    return markers.get(model_tag, 'o')

def load_results():
    results = {}
    all_models = list(set(COMPARISON_METHODS + [f"QC{d}" for d in QC_DEGREES]))
    for model_tag in all_models:
        results[model_tag] = {}
        for node_count in NODE_COUNTS:
            csv_path = Path(RESULTS_DIR) / f"{model_tag}_{node_count}_results.csv"
            if not csv_path.exists():
                continue
            df = pd.read_csv(csv_path)
            if len(df) == 0:
                continue
            if 'elapsed_time' in df.columns and 'solve_time' in df.columns:
                df['overhead'] = df['elapsed_time'] - df['solve_time']
            avg_metrics = {}
            for col in df.columns:
                if col != 'batch_index':
                    valid_values = df[col].dropna()
                    if len(valid_values) > 0:
                        avg_metrics[col] = valid_values.mean()
                    else:
                        avg_metrics[col] = np.nan
            results[model_tag][node_count] = avg_metrics
    return results


# Configuration
RESULTS_DIR = "relaxation_results"
OUTPUT_DIR = Path(RESULTS_DIR) / "plots"
NODE_COUNTS = [32 * n for n in range(1, 21)]  # 32, 64, 96, ..., 640 (but 640 is actually 617)
# For plotting: show 617 instead of 640 in tick labels, but keep tick at 640 position
XTICK_POSITIONS = NODE_COUNTS
XTICK_LABELS = [str(n) if n != 640 else '617' for n in NODE_COUNTS]

# Methods for comprehensive comparison
COMPARISON_METHODS = ["DCOPF", "Jabr", "Shor", "ChordalShor", "QC6"]

# QC degrees for sensitivity analysis
QC_DEGREES = [4, 6, 8, 10]

# Marker size for plotted nodes (reduce to make nodes smaller)
PLOT_MARKER_SIZE = 4


# --- New: Split into 3 separate plots, each with 2 subplots ---
def create_figure1a(results, output_dir):
    """(a) Solve Time, (b) Overhead"""
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(14, 5))

    # (a) Solve Time
    for method in COMPARISON_METHODS:
        if method not in results:
            continue
        node_counts = []
        solve_times = []
        for nc in sorted(results[method].keys()):
            solve_time = results[method][nc].get('solve_time', np.nan)
            if not np.isnan(solve_time):
                node_counts.append(nc)
                solve_times.append(solve_time)
        if len(node_counts) > 0:
            ax_a.plot(node_counts, solve_times, marker=get_marker(method), markersize=PLOT_MARKER_SIZE,
                     linewidth=2.5, label=method, color=get_color(method), alpha=0.85)
    ax_a.set_xlabel('Number of Nodes', fontsize=13, fontweight='bold')
    ax_a.set_ylabel('Solve Time (s)', fontsize=13, fontweight='bold')
    ax_a.set_xticks(XTICK_POSITIONS)
    ax_a.set_xticklabels(XTICK_LABELS)
    ax_a.set_title('(a) Solve Time vs Network Size', fontsize=14, fontweight='bold', loc='left')
    ax_a.set_yscale('log')
    ax_a.grid(True, which='both', alpha=0.5, linestyle='--')
    ax_a.legend(fontsize=9, framealpha=0.95, loc='best', edgecolor='black', fancybox=False)

    # (b) Overhead
    for method in COMPARISON_METHODS:
        if method not in results:
            continue
        node_counts = []
        overheads = []
        for nc in sorted(results[method].keys()):
            overhead = results[method][nc].get('overhead', np.nan)
            if not np.isnan(overhead):
                node_counts.append(nc)
                overheads.append(overhead)
        if len(node_counts) > 0:
            ax_b.plot(node_counts, overheads, marker=get_marker(method), markersize=PLOT_MARKER_SIZE,
                     linewidth=2.5, label=method, color=get_color(method), alpha=0.85)
    ax_b.set_xlabel('Number of Nodes', fontsize=13, fontweight='bold')
    ax_b.set_ylabel('Overhead (s)', fontsize=13, fontweight='bold')
    ax_b.set_xticks(XTICK_POSITIONS)
    ax_b.set_xticklabels(XTICK_LABELS)
    ax_b.set_title('(b) Overhead vs Network Size', fontsize=14, fontweight='bold', loc='left')
    ax_b.set_yscale('log')
    ax_b.grid(True, which='both', alpha=0.5, linestyle='--')
    ax_b.legend(fontsize=9, framealpha=0.95, loc='best', edgecolor='black', fancybox=False)

    plt.suptitle('Comparison of Relaxations: Solve Time & Overhead', fontsize=16, fontweight='bold', y=0.995)
    plt.tight_layout()
    output_path_png = Path(output_dir) / 'solve_time_overhead.png'
    plt.savefig(output_path_png, dpi=300, bbox_inches='tight')
    print(f"  Saved: {output_path_png}")
    plt.close()

def create_figure1b(results, output_dir):
    """(c) Memory Usage, (d) Welfare"""
    fig, (ax_c, ax_d) = plt.subplots(1, 2, figsize=(14, 5))

    # (c) Memory Usage
    for method in COMPARISON_METHODS:
        if method not in results:
            continue
        node_counts = []
        memories = []
        for nc in sorted(results[method].keys()):
            memory = results[method][nc].get('peak_memory_usage', np.nan)
            if not np.isnan(memory):
                node_counts.append(nc)
                memories.append(memory / 1024.0)  # Convert to GB
        if len(node_counts) > 0:
            ax_c.plot(node_counts, memories, marker=get_marker(method), markersize=PLOT_MARKER_SIZE,
                     linewidth=2.5, label=method, color=get_color(method), alpha=0.85)
    ax_c.set_xlabel('Number of Nodes', fontsize=13, fontweight='bold')
    ax_c.set_ylabel('Peak Memory (GB)', fontsize=13, fontweight='bold')
    ax_c.set_xticks(XTICK_POSITIONS)
    ax_c.set_xticklabels(XTICK_LABELS)
    ax_c.set_title('(c) Memory Usage vs Network Size', fontsize=14, fontweight='bold', loc='left')
    ax_c.grid(True, which='both', alpha=0.5, linestyle='--')
    ax_c.legend(fontsize=9, framealpha=0.95, loc='upper left', edgecolor='black', fancybox=False)
    ax_c.set_yscale('log')

    # (d) Welfare
    for method in COMPARISON_METHODS:
        if method not in results:
            continue
        node_counts = []
        welfares = []
        for nc in sorted(results[method].keys()):
            welfare = results[method][nc].get('welfare', np.nan)
            if not np.isnan(welfare):
                node_counts.append(nc)
                welfares.append(welfare)
        if len(node_counts) > 0:
            ax_d.plot(node_counts, welfares, marker=get_marker(method), markersize=PLOT_MARKER_SIZE,
                     linewidth=2.5, label=method, color=get_color(method), alpha=0.85)
    ax_d.set_xlabel('Network Size (nodes)', fontsize=13, fontweight='bold')
    ax_d.set_ylabel('Welfare (objective value)', fontsize=13, fontweight='bold')
    ax_d.set_title('(d) Welfare vs Network Size', fontsize=14, fontweight='bold', loc='left')
    ax_d.set_xticks(XTICK_POSITIONS)
    ax_d.set_xticklabels(XTICK_LABELS)
    ax_d.set_yscale('log')
    ax_d.grid(True, which='both', alpha=0.5, linestyle='--')
    ax_d.legend(fontsize=9, framealpha=0.95, loc='best', edgecolor='black', fancybox=False)

    plt.suptitle('Comparison of Relaxations: Memory & Welfare', fontsize=16, fontweight='bold', y=0.995)
    plt.tight_layout()
    output_path_png = Path(output_dir) / 'memory_welfare.png'
    plt.savefig(output_path_png, dpi=300, bbox_inches='tight')
    print(f"  Saved: {output_path_png}")
    plt.close()

def create_figure1c(results, output_dir):
    """(e) Current Phasor Error, (f) Thermal Limit Violation"""
    fig, (ax_e, ax_f) = plt.subplots(1, 2, figsize=(14, 5))

    # (e) Current Phasor Error
    for method in COMPARISON_METHODS:
        if method not in results:
            continue
        node_counts = []
        violations = []
        for nc in sorted(results[method].keys()):
            viol = results[method][nc].get('line (A)', np.nan)
            if not np.isnan(viol):
                node_counts.append(nc)
                violations.append(viol)
        if len(node_counts) > 0:
            ax_e.plot(node_counts, violations, marker=get_marker(method), markersize=PLOT_MARKER_SIZE,
                     linewidth=2.5, label=method, color=get_color(method), alpha=0.85)
    ax_e.set_xlabel('Network Size (nodes)', fontsize=13, fontweight='bold')
    ax_e.set_ylabel('Avg Current Phasor Error (A)', fontsize=13, fontweight='bold')
    ax_e.set_title('(e) Current Phasor Error vs Network Size', fontsize=14, fontweight='bold', loc='left')
    ax_e.set_xticks(XTICK_POSITIONS)
    ax_e.set_xticklabels(XTICK_LABELS)
    ax_e.set_yscale('log')
    ax_e.grid(True, which='both', alpha=0.5, linestyle='--')
    ax_e.legend(fontsize=9, framealpha=0.95, loc='best', edgecolor='black', fancybox=False)

    # (f) Thermal Limit Violation
    for method in COMPARISON_METHODS:
        if method not in results:
            continue
        node_counts = []
        violations = []
        for nc in sorted(results[method].keys()):
            viol = results[method][nc].get('line_current_limit (A)', np.nan)
            if not np.isnan(viol):
                node_counts.append(nc)
                violations.append(viol)
        if len(node_counts) > 0:
            ax_f.plot(node_counts, violations, marker=get_marker(method), markersize=PLOT_MARKER_SIZE,
                     linewidth=2.5, label=method, color=get_color(method), alpha=0.85)
    ax_f.set_xlabel('Network Size (nodes)', fontsize=13, fontweight='bold')
    ax_f.set_ylabel('Avg Thermal Limit Violation (A)', fontsize=13, fontweight='bold')
    ax_f.set_title('(f) Thermal Limit Violation vs Network Size', fontsize=14, fontweight='bold', loc='left')
    ax_f.set_xticks(XTICK_POSITIONS)
    ax_f.set_xticklabels(XTICK_LABELS)
    ax_f.grid(True, which='both', alpha=0.5, linestyle='--')
    ax_f.legend(fontsize=9, framealpha=0.95, loc='best', edgecolor='black', fancybox=False)

    plt.suptitle('Comparison of Relaxations: Current Phasor Errors & Thermal Limit Violations', fontsize=16, fontweight='bold', y=0.995)
    plt.tight_layout()
    output_path_png = Path(output_dir) / 'current_phasor_thermal_limit_violations.png'
    plt.savefig(output_path_png, dpi=300, bbox_inches='tight')
    print(f"  Saved: {output_path_png}")
    plt.close()


def create_figure2_qc_sensitivity(results, output_dir):
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(14, 5))
    
    degrees_and_jabr = ['Jabr', 'QC4', 'QC6', 'QC8', 'QC10']

    # Panel (a): Memory vs Network Size (Curve Plot) - x-axis: network size, curve for each degree
    for model in degrees_and_jabr:
        x_vals = []
        y_vals = []
        for size in XTICK_POSITIONS:
            if model in results and size in results[model]:
                mem = results[model][size].get('welfare', np.nan)
                if not np.isnan(mem):
                    x_vals.append(size)
                    # Stored value in CSV is MB; convert MB -> GB for plotting
                    y_vals.append(mem / 1024.0)  # Convert to GB
        if len(x_vals) > 0:
            linestyle = '--' if model == 'Jabr' else '-'
            ax_a.plot(x_vals, y_vals, marker=get_marker(model), markersize=2,
                      linewidth=1.2, label=model, color=get_color(model), alpha=0.85, linestyle=linestyle)

    ax_a.set_xlabel('Network Size (nodes)', fontsize=13, fontweight='bold')
    ax_a.set_ylabel('Welfare (objective value)', fontsize=13, fontweight='bold')
    ax_a.set_title('(a) Welfare', fontsize=14, fontweight='bold', loc='left')
    ax_a.set_xticks(XTICK_POSITIONS)
    ax_a.set_xticklabels(XTICK_LABELS)
    ax_a.set_yscale('log')
    ax_a.grid(True, which='both', alpha=0.5, linestyle='--')
    ax_a.legend(fontsize=9, framealpha=0.95, loc='upper left',
               edgecolor='black', fancybox=False)
    
    # Panel (b): Line Current Phasor Errors with x-axis = network sizes, curve plot for each degree + Jabr
    # The "line (A)" metric measures how much the model-reported complex current phasor
    # differs from physical reality imposed by voltages, averaged over all lines

    for model in degrees_and_jabr:
        if model not in results:
            continue
        node_counts = []
        violations = []
        for nc in sorted(results[model].keys()):
            viol = results[model][nc].get('line (A)', np.nan)
            if not np.isnan(viol):
                node_counts.append(nc)
                violations.append(viol)
        if len(node_counts) > 0:
            linestyle = '--' if model == 'Jabr' else '-'
            ax_b.plot(node_counts, violations, marker=get_marker(model), markersize=2,
                     linewidth=1.2, label=model, color=get_color(model), alpha=0.85, linestyle=linestyle)

    ax_b.set_xlabel('Network Size (nodes)', fontsize=13, fontweight='bold')
    ax_b.set_ylabel('Avg Current Phasor Error (A)', fontsize=13, fontweight='bold')
    ax_b.set_title('(b) Current Phasor Errors', fontsize=14, fontweight='bold', loc='left')
    ax_b.set_xticks(XTICK_POSITIONS)
    ax_b.set_xticklabels(XTICK_LABELS)
    ax_b.set_yscale('log')
    ax_b.grid(True, which='both', alpha=0.5, linestyle='--')
    ax_b.legend(fontsize=9, framealpha=0.95, loc='best',
           edgecolor='black', fancybox=False)
    
    plt.suptitle('Comparison of QC Relaxations with Local QMC Sampling', fontsize=17, fontweight='bold', y=0.995)
    plt.tight_layout()
    
    output_path_png = Path(output_dir) / 'local_qmc_sampling.png'
    plt.savefig(output_path_png, dpi=300, bbox_inches='tight')
    print(f"  Saved: {output_path_png}")
    plt.close()


if __name__ == "__main__":
    results = load_results()
    
    print(f"Loaded results for {len(results)} models")
    print(f"Models: {', '.join(sorted(results.keys()))}")
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("\n[1/4] Creating Figure 1a (Solve Time & Overhead)...")
    create_figure1a(results, OUTPUT_DIR)
    print("\n[2/4] Creating Figure 1b (Memory & Welfare)...")
    create_figure1b(results, OUTPUT_DIR)
    print("\n[3/4] Creating Figure 1c (Phasor & Thermal Violation)...")
    create_figure1c(results, OUTPUT_DIR)
    
    print("\n[2/2] Creating Figure 2: QC Degree Sensitivity Analysis (3-panel)...")
    create_figure2_qc_sensitivity(results, OUTPUT_DIR)
    
    print("\n" + "="*80)
    print("PROCESSING COMPLETE")
    print("="*80)
    print(f"\nOutput directory: {OUTPUT_DIR}/")
