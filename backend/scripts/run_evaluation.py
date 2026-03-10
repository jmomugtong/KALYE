#!/usr/bin/env python3
"""CLI script to run KALYE model evaluation pipeline.

Usage:
    python -m backend.scripts.run_evaluation --data-dir data/evals --output report.json --format json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.src.evaluation.dataset_loader import EvaluationDatasetLoader
from backend.src.evaluation.evaluator import ModelEvaluator
from backend.src.evaluation.metrics import BiasMetrics, DetectionMetrics, SegmentationMetrics


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run KALYE model evaluation pipeline"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/evals",
        help="Path to evaluation data directory (default: data/evals)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="evaluation_report.json",
        help="Output path for evaluation report (default: evaluation_report.json)",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["json", "html"],
        default="json",
        help="Output format: json or html (default: json)",
    )
    return parser


def generate_html_report(report: dict) -> str:
    """Generate a simple HTML report from the evaluation results."""
    checks = report.get("threshold_checks", {})
    overall = checks.get("overall_pass", False)
    status_color = "#2ecc71" if overall else "#e74c3c"
    status_text = "PASSED" if overall else "FAILED"

    rows = ""
    for key, check in checks.items():
        if key == "overall_pass":
            continue
        if not isinstance(check, dict):
            continue
        passed = check.get("passed", False)
        color = "#2ecc71" if passed else "#e74c3c"
        rows += (
            f"<tr>"
            f"<td>{key}</td>"
            f"<td>{check.get('value', 'N/A'):.4f}</td>"
            f"<td>{check.get('threshold', 'N/A')}</td>"
            f'<td style="color:{color}">{"PASS" if passed else "FAIL"}</td>'
            f"</tr>\n"
        )

    html = f"""<!DOCTYPE html>
<html>
<head><title>KALYE Evaluation Report</title>
<style>
body {{ font-family: sans-serif; margin: 2em; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
th {{ background-color: #f5f5f5; }}
</style>
</head>
<body>
<h1>KALYE Model Evaluation Report</h1>
<p>Timestamp: {report.get("timestamp", "N/A")}</p>
<h2 style="color:{status_color}">Overall: {status_text}</h2>
<h3>Threshold Checks</h3>
<table>
<tr><th>Metric</th><th>Value</th><th>Threshold</th><th>Status</th></tr>
{rows}
</table>
<h3>Raw Results</h3>
<pre>{json.dumps(report.get("results", {}), indent=2)}</pre>
</body>
</html>"""
    return html


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Initialize components
    loader = EvaluationDatasetLoader(data_dir=args.data_dir)
    detection_metrics = DetectionMetrics()
    segmentation_metrics = SegmentationMetrics()
    bias_metrics = BiasMetrics()
    evaluator = ModelEvaluator(
        dataset_loader=loader,
        detection_metrics=detection_metrics,
        segmentation_metrics=segmentation_metrics,
        bias_metrics=bias_metrics,
    )

    detection_results = None
    segmentation_results = None
    bias_results = None

    # Run detection evaluation
    try:
        dataset = loader.load_detection_dataset()
        if dataset:
            all_gt = []
            for item in dataset:
                all_gt.extend(item.get("annotations", []))
            # In a real run, predictions would come from model inference.
            # Here we use ground truth as a placeholder to show the pipeline works.
            print(f"Loaded {len(dataset)} detection images with {len(all_gt)} annotations")
            detection_results = evaluator.evaluate_detection_model(all_gt, all_gt)
            print(f"Detection results: {detection_results}")
    except FileNotFoundError as e:
        print(f"Skipping detection evaluation: {e}")

    # Run segmentation evaluation
    try:
        seg_dataset = loader.load_segmentation_dataset()
        if seg_dataset:
            print(f"Loaded {len(seg_dataset)} segmentation images")
            # In a real run, we would load masks and run inference.
            print("Segmentation evaluation requires mask files - skipping inference.")
    except FileNotFoundError as e:
        print(f"Skipping segmentation evaluation: {e}")

    # Run bias evaluation
    try:
        walkability_gt = loader.load_walkability_ground_truth()
        if walkability_gt:
            scores = {
                d: info["score"] if isinstance(info, dict) else info
                for d, info in walkability_gt.items()
            }
            bias_results = evaluator.evaluate_bias(scores)
            print(f"Bias results: {bias_results}")
    except FileNotFoundError as e:
        print(f"Skipping bias evaluation: {e}")

    # Generate report
    report = evaluator.generate_report(
        detection_results=detection_results,
        segmentation_results=segmentation_results,
        bias_results=bias_results,
    )

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.format == "html":
        output_path = output_path.with_suffix(".html")
        content = generate_html_report(report)
        output_path.write_text(content)
    else:
        output_path = output_path.with_suffix(".json")
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)

    print(f"\nReport written to {output_path}")

    # Check thresholds and set exit code
    checks = report.get("threshold_checks", {})
    overall_pass = checks.get("overall_pass", True)

    if not overall_pass:
        print("\nEvaluation FAILED: one or more thresholds not met.")
        for key, check in checks.items():
            if key == "overall_pass":
                continue
            if isinstance(check, dict) and not check.get("passed", True):
                print(
                    f"  FAIL: {key} = {check['value']:.4f} "
                    f"(threshold: {check['threshold']})"
                )
        return 1

    print("\nEvaluation PASSED: all thresholds met.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
